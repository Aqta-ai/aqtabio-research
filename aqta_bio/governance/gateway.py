"""
Governance Gateway module implementing the 8-layer governance framework.

This module provides the GovernanceGateway class that enforces:
1. Audit logging (Task 7.1) - implemented in audit.py
2. Model SHA verification (Task 7.2) - implemented here
3. Circuit breaker for data staleness (Task 7.3)
4. Human-in-the-loop sign-off (Task 7.4)
5. Confidence bands (implemented in model layer)
6. RBAC (Task 7.5)
7. SHAP explanations (implemented in model layer)
8. Bias monitoring (Task 7.6)

Validates: Requirement 6 (Governance Gateway)
"""

from __future__ import annotations

import hashlib
import logging
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from aqta_bio.config import get_database_url
from aqta_bio.governance.audit import log_prediction_audit

logger = logging.getLogger(__name__)


class ModelIntegrityError(Exception):
    """Raised when model SHA verification fails."""
    pass


class DataStalenessWarning(Warning):
    """Warning for stale feature data."""
    pass


@dataclass
class ModelVerificationResult:
    """Result of model SHA verification."""
    verified: bool
    expected_sha: str
    actual_sha: str
    model_id: str
    message: str


class GovernanceGateway:
    """
    Governance Gateway enforcing the 8-layer governance framework.
    
    This class provides methods for:
    - Model SHA verification (Requirement 6.2)
    - Circuit breaker for data staleness (Requirement 6.3)
    - Human-in-the-loop sign-off (Requirement 6.4)
    - RBAC enforcement (Requirement 6.6)
    - Bias auditing (Requirement 6.8)
    
    Example:
        >>> gateway = GovernanceGateway()
        >>> gateway.verify_model(model, expected_sha="abc123...")
        >>> warning = gateway.check_circuit_breaker("AF-025-12345", datetime.now())
        >>> needs_signoff = gateway.require_hitl_signoff("AF-025-12345", 0.95)
    """
    
    def __init__(self, engine: Optional[Engine] = None):
        """
        Initialize Governance Gateway.
        
        Args:
            engine: SQLAlchemy engine (created if not provided)
        """
        if engine is None:
            db_url = get_database_url()
            self.engine = create_engine(db_url)
        else:
            self.engine = engine
    
    def verify_model(
        self,
        model: Any,
        expected_sha: str,
        model_id: str,
        raise_on_mismatch: bool = True,
    ) -> ModelVerificationResult:
        """
        Verify model artifact SHA-256 hash matches expected value.
        
        This method implements Requirement 6.2:
        "WHEN a model is registered or updated, THE Governance_Gateway SHALL
        verify the model artifact SHA hash matches the Model_Registry record
        and reject any unverified model."
        
        The verification process:
        1. Compute SHA-256 hash of the pickled model artifact
        2. Compare with expected hash from MLflow registry
        3. Raise ModelIntegrityError if mismatch (when raise_on_mismatch=True)
        4. Return verification result with details
        
        Args:
            model: Loaded model object to verify
            expected_sha: Expected SHA-256 hash from MLflow registry
            model_id: Model identifier for error messages
            raise_on_mismatch: If True, raise exception on hash mismatch
        
        Returns:
            ModelVerificationResult with verification status and details
        
        Raises:
            ModelIntegrityError: If hash mismatch and raise_on_mismatch=True
        
        Validates: Requirement 6.2
        
        Example:
            >>> gateway = GovernanceGateway()
            >>> result = gateway.verify_model(
            ...     model=xgb_model,
            ...     expected_sha="abc123...",
            ...     model_id="ebola_xgboost_20240115"
            ... )
            >>> if result.verified:
            ...     print("Model verified successfully")
        """
        # Compute actual SHA-256 hash of model
        model_bytes = pickle.dumps(model)
        actual_sha = hashlib.sha256(model_bytes).hexdigest()
        
        # Compare hashes
        verified = actual_sha == expected_sha
        
        if verified:
            message = f"Model {model_id} verified successfully (SHA: {actual_sha[:16]}...)"
            result = ModelVerificationResult(
                verified=True,
                expected_sha=expected_sha,
                actual_sha=actual_sha,
                model_id=model_id,
                message=message,
            )
            logger.info("Model verified: %s", message)
            return result
        else:
            message = (
                f"Model integrity check FAILED for {model_id}\n"
                f"Expected SHA: {expected_sha[:16]}...\n"
                f"Actual SHA:   {actual_sha[:16]}...\n"
                f"This model artifact does not match the registered version."
            )
            
            result = ModelVerificationResult(
                verified=False,
                expected_sha=expected_sha,
                actual_sha=actual_sha,
                model_id=model_id,
                message=message,
            )
            
            if raise_on_mismatch:
                raise ModelIntegrityError(message)
            else:
                logger.error("Model integrity mismatch: %s", message)
                return result
    
    def verify_model_from_mlflow(
        self,
        run_id: str,
        model_path: str = "model",
        raise_on_mismatch: bool = True,
    ) -> tuple[Any, ModelVerificationResult]:
        """
        Load model from MLflow and verify its SHA hash.
        
        This is a convenience method that:
        1. Loads the model from MLflow using run_id
        2. Retrieves the expected SHA hash from MLflow run parameters
        3. Verifies the model using verify_model()
        
        Args:
            run_id: MLflow run ID
            model_path: Path to model artifact within run (default: "model")
            raise_on_mismatch: If True, raise exception on hash mismatch
        
        Returns:
            Tuple of (loaded_model, verification_result)
        
        Raises:
            ModelIntegrityError: If hash mismatch and raise_on_mismatch=True
        
        Example:
            >>> gateway = GovernanceGateway()
            >>> model, result = gateway.verify_model_from_mlflow(
            ...     run_id="abc123def456",
            ...     raise_on_mismatch=True
            ... )
        """
        # Load model from MLflow (lazy import — keeps Lambda cold start fast)
        import mlflow
        import mlflow.sklearn
        import mlflow.xgboost

        model_uri = f"runs:/{run_id}/{model_path}"

        try:
            model = mlflow.xgboost.load_model(model_uri)
        except Exception:
            model = mlflow.sklearn.load_model(model_uri)

        # Get expected SHA from MLflow run parameters
        client = mlflow.tracking.MlflowClient()
        run = client.get_run(run_id)
        expected_sha = run.data.params.get("sha_hash")
        model_id = run.data.params.get("model_id", run_id)
        
        if expected_sha is None:
            raise ValueError(
                f"No sha_hash parameter found in MLflow run {run_id}. "
                "Model was not registered with SHA verification."
            )
        
        # Verify model
        result = self.verify_model(
            model=model,
            expected_sha=expected_sha,
            model_id=model_id,
            raise_on_mismatch=raise_on_mismatch,
        )
        
        return model, result
    
    def check_circuit_breaker(
        self,
        tile_id: str,
        feature_freshness: datetime,
        staleness_threshold_days: int = 90,
    ) -> Optional[str]:
        """
        Check if tile's feature data is stale and return warning if needed.
        
        This method implements Requirement 6.3:
        "WHILE a Tile's underlying feature data is older than 90 days,
        THE Governance_Gateway SHALL flag that Tile's predictions with a
        'Data Stale — do not use for decisions' warning via the Circuit_Breaker."
        
        Args:
            tile_id: Tile identifier
            feature_freshness: Timestamp of most recent feature data
            staleness_threshold_days: Days threshold for staleness (default: 90)
        
        Returns:
            Warning string if data is stale, None otherwise
        
        Validates: Requirement 6.3
        
        Example:
            >>> gateway = GovernanceGateway()
            >>> warning = gateway.check_circuit_breaker(
            ...     tile_id="AF-025-12345",
            ...     feature_freshness=datetime(2023, 10, 1),
            ...     staleness_threshold_days=90
            ... )
            >>> if warning:
            ...     print(f"Warning: {warning}")
        """
        now = datetime.now()
        age_days = (now - feature_freshness).days
        
        if age_days > staleness_threshold_days:
            warning = (
                f"Data Stale — do not use for decisions. "
                f"Feature data for tile {tile_id} is {age_days} days old "
                f"(threshold: {staleness_threshold_days} days). "
                f"Last updated: {feature_freshness.strftime('%Y-%m-%d')}"
            )
            return warning
        
        return None
    
    def require_hitl_signoff(
        self,
        tile_id: str,
        risk_score: float,
        pathogen_id: str = "ebola",
        month: Optional[str] = None,
        top_percentile_threshold: float = 0.01,
    ) -> dict:
        """
        Check if tile requires human-in-the-loop epidemiologist sign-off.
        
        This method implements Requirement 6.4:
        "WHEN a Tile enters the top-1% risk tier, THE Governance_Gateway SHALL
        require epidemiologist sign-off before any external alert is issued
        for that Tile."
        
        If the tile is in the top-1% risk tier and no sign-off exists,
        creates a pending sign-off requirement in the database.
        
        Args:
            tile_id: Tile identifier
            risk_score: Predicted risk score [0, 1]
            pathogen_id: Pathogen identifier (default: "ebola")
            month: Month in YYYY-MM format (default: current month)
            top_percentile_threshold: Percentile threshold (default: 0.01 for top-1%)
        
        Returns:
            Dictionary with:
                - requires_signoff: bool - True if tile is in top-1%
                - signoff_status: str - "pending", "approved", "rejected", or None
                - approved_for_alert: bool - True if approved for external alerts
                - signoff_id: int or None - Database ID of sign-off record
        
        Validates: Requirement 6.4
        
        Example:
            >>> gateway = GovernanceGateway()
            >>> result = gateway.require_hitl_signoff(
            ...     tile_id="AF-025-12345",
            ...     risk_score=0.95,
            ...     pathogen_id="ebola",
            ...     month="2026-06"
            ... )
            >>> if result["requires_signoff"] and not result["approved_for_alert"]:
            ...     print("Epidemiologist sign-off required before external alert")
        """
        from datetime import datetime
        from aqta_bio.governance.hitl import HITLSignoffService
        
        # Determine if tile is in top-1% risk tier
        threshold_score = 1.0 - top_percentile_threshold
        requires_signoff = risk_score >= threshold_score
        
        # Default month to current month if not provided
        if month is None:
            month = datetime.utcnow().strftime("%Y-%m")
        
        # If tile doesn't require sign-off, return early
        if not requires_signoff:
            return {
                "requires_signoff": False,
                "signoff_status": None,
                "approved_for_alert": True,  # No sign-off needed, can alert
                "signoff_id": None,
            }
        
        # Tile requires sign-off - check database for existing sign-off
        if self.engine is None:
            # No database connection - return conservative result
            return {
                "requires_signoff": True,
                "signoff_status": "pending",
                "approved_for_alert": False,
                "signoff_id": None,
            }
        
        from sqlalchemy.orm import Session
        
        with Session(self.engine) as session:
            service = HITLSignoffService(session)
            
            # Check if sign-off already exists
            signoff = service.get_signoff_status(tile_id, pathogen_id, month)
            
            if signoff is None:
                # Create new sign-off requirement
                signoff = service.create_signoff_requirement(
                    tile_id=tile_id,
                    pathogen_id=pathogen_id,
                    month=month,
                    risk_score=risk_score,
                )
            
            return {
                "requires_signoff": True,
                "signoff_status": signoff.status,
                "approved_for_alert": signoff.status == "approved",
                "signoff_id": signoff.id,
            }
    
    def enforce_rbac(
        self,
        user_role: str,
        action: str,
    ) -> bool:
        """
        Enforce role-based access control.
        
        This method implements Requirement 6.6:
        "WHEN a user accesses the system, THE Governance_Gateway SHALL enforce
        role-based access control: Researcher (read), Public Health Officer
        (read + export), Admin (retrain)."
        
        Role permissions:
        - Researcher: read
        - Public Health Officer (PHO): read, export
        - Admin: read, export, retrain, approve_alert
        
        Args:
            user_role: User role ("researcher", "pho", "admin")
            action: Action to perform ("read", "export", "retrain", "approve_alert")
        
        Returns:
            True if action is allowed, False otherwise
        
        Validates: Requirement 6.6
        
        Example:
            >>> gateway = GovernanceGateway()
            >>> allowed = gateway.enforce_rbac(
            ...     user_role="researcher",
            ...     action="export"
            ... )
            >>> if not allowed:
            ...     raise PermissionError("Action not allowed")
        """
        # Define role permissions
        permissions = {
            "researcher": {"read"},
            "pho": {"read", "export"},
            "admin": {"read", "export", "retrain", "approve_alert"},
        }
        
        user_role_lower = user_role.lower()
        action_lower = action.lower()
        
        if user_role_lower not in permissions:
            return False
        
        return action_lower in permissions[user_role_lower]
    
    def log_prediction(
        self,
        tile_id: str,
        risk_score: float,
        confidence_p10: float,
        confidence_p90: float,
        model_version: str,
        feature_hash: str,
        user_id: str = "system",
    ) -> int:
        """
        Log prediction to audit trail.
        
        Convenience wrapper around log_prediction_audit from audit.py.
        
        Args:
            tile_id: Tile identifier
            risk_score: Predicted risk score
            confidence_p10: 10th percentile confidence bound
            confidence_p90: 90th percentile confidence bound
            model_version: Model version identifier
            feature_hash: SHA-256 hash of features
            user_id: User identifier
        
        Returns:
            Audit log entry ID
        
        Validates: Requirement 6.1
        """
        return log_prediction_audit(
            tile_id=tile_id,
            risk_score=risk_score,
            confidence_p10=confidence_p10,
            confidence_p90=confidence_p90,
            model_version=model_version,
            feature_hash=feature_hash,
            user_id=user_id,
            action="predict",
            engine=self.engine,
        )
    
    def run_bias_audit(
        self,
        predictions: "pd.DataFrame",
        tile_income_groups: "pd.Series",
        threshold: float = 15.0,
    ) -> "BiasReport":
        """
        Run quarterly bias audit across income groups.
        
        This method implements Requirement 6.8:
        "WHEN a quarterly bias audit runs, THE Governance_Gateway SHALL compute
        recall across LIC, LMIC, and HIC tile groups and flag any recall gap
        exceeding 15 percentage points."
        
        The audit computes recall (TP / (TP + FN)) for each income group
        (Low Income Countries, Lower-Middle Income Countries, High Income Countries)
        and flags if the gap between highest and lowest recall exceeds the threshold.
        
        Args:
            predictions: DataFrame with columns:
                - tile_id: Tile identifier
                - y_true: Ground truth labels (0 or 1)
                - y_pred: Predicted labels (0 or 1)
            tile_income_groups: Series mapping tile_id to income group
                ("LIC", "LMIC", or "HIC")
            threshold: Recall gap threshold in percentage points (default: 15.0)
        
        Returns:
            BiasReport with recall metrics and flagging status
        
        Validates: Requirement 6.8
        
        Example:
            >>> gateway = GovernanceGateway()
            >>> predictions = pd.DataFrame({
            ...     'tile_id': ['AF-025-001', 'AF-025-002'],
            ...     'y_true': [1, 1],
            ...     'y_pred': [1, 0]
            ... })
            >>> income_groups = pd.Series({
            ...     'AF-025-001': 'LIC',
            ...     'AF-025-002': 'LMIC'
            ... })
            >>> report = gateway.run_bias_audit(predictions, income_groups)
            >>> if report.flagged:
            ...     print(f"Bias detected: {report.message}")
        """
        from aqta_bio.governance.bias_audit import run_bias_audit
        
        return run_bias_audit(
            predictions=predictions,
            tile_income_groups=tile_income_groups,
            threshold=threshold,
        )
    
    def check_model_staleness(
        self,
        pathogen_id: str = "ebola",
        staleness_threshold_months: int = 12,
    ) -> dict:
        """
        Check if active production model requires retraining.
        
        This method implements Requirement 6.9:
        "WHEN a model has been in production for more than 12 months without
        retraining, THE Governance_Gateway SHALL flag the model as 'Due for
        retraining' in the audit log and Dashboard."
        
        The check determines staleness based on:
        1. Time since initial deployment (if never retrained)
        2. Time since last retraining (if previously retrained)
        
        Args:
            pathogen_id: Pathogen identifier (default: "ebola")
            staleness_threshold_months: Months threshold for staleness (default: 12)
        
        Returns:
            Dictionary with:
                - is_stale: bool - True if model needs retraining
                - deployment_id: int or None - Database ID of deployment
                - model_id: str or None - Model identifier
                - age_months: float or None - Age in months since last training
                - deployed_at: datetime or None - Initial deployment timestamp
                - last_retrained_at: datetime or None - Last retraining timestamp
                - warning: str or None - Warning message if stale
        
        Validates: Requirement 6.9
        
        Example:
            >>> gateway = GovernanceGateway()
            >>> result = gateway.check_model_staleness(pathogen_id="ebola")
            >>> if result["is_stale"]:
            ...     print(f"Warning: {result['warning']}")
            ...     # Trigger retraining via Admin API
        """
        if self.engine is None:
            return {
                "is_stale": False,
                "deployment_id": None,
                "model_id": None,
                "age_months": None,
                "deployed_at": None,
                "last_retrained_at": None,
                "warning": None,
            }
        
        from sqlalchemy import text
        
        # Query for active model deployment
        query = text("""
            SELECT 
                id,
                model_id,
                deployed_at,
                last_retrained_at,
                COALESCE(last_retrained_at, deployed_at) as effective_training_date
            FROM model_deployments
            WHERE pathogen_id = :pathogen_id
                AND status = 'active'
            ORDER BY deployed_at DESC
            LIMIT 1
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {"pathogen_id": pathogen_id}).fetchone()
        
        if result is None:
            # No active deployment found
            return {
                "is_stale": False,
                "deployment_id": None,
                "model_id": None,
                "age_months": None,
                "deployed_at": None,
                "last_retrained_at": None,
                "warning": None,
            }
        
        deployment_id = result[0]
        model_id = result[1]
        deployed_at = result[2]
        last_retrained_at = result[3]
        effective_training_date = result[4]
        
        # Calculate age in months
        now = datetime.now()
        age_delta = now - effective_training_date
        age_months = age_delta.days / 30.44  # Average days per month
        
        is_stale = age_months > staleness_threshold_months
        
        if is_stale:
            training_type = "retrained" if last_retrained_at else "deployed"
            warning = (
                f"Model {model_id} for {pathogen_id} is due for retraining. "
                f"Last {training_type} {age_months:.1f} months ago "
                f"(threshold: {staleness_threshold_months} months). "
                f"Use Admin API endpoint POST /admin/models/retrain to trigger retraining."
            )
        else:
            warning = None
        
        return {
            "is_stale": is_stale,
            "deployment_id": deployment_id,
            "model_id": model_id,
            "age_months": age_months,
            "deployed_at": deployed_at,
            "last_retrained_at": last_retrained_at,
            "warning": warning,
        }
    
    def flag_stale_model_in_audit_log(
        self,
        pathogen_id: str = "ebola",
        user_id: str = "system",
    ) -> Optional[int]:
        """
        Flag stale model in audit log if retraining is needed.
        
        This method checks model staleness and creates an audit log entry
        if the model is due for retraining.
        
        Args:
            pathogen_id: Pathogen identifier (default: "ebola")
            user_id: User identifier (default: "system")
        
        Returns:
            Audit log entry ID if model is stale, None otherwise
        
        Validates: Requirement 6.9
        
        Example:
            >>> gateway = GovernanceGateway()
            >>> audit_id = gateway.flag_stale_model_in_audit_log("ebola")
            >>> if audit_id:
            ...     print(f"Stale model flagged in audit log (ID: {audit_id})")
        """
        staleness_check = self.check_model_staleness(pathogen_id)
        
        if not staleness_check["is_stale"]:
            return None
        
        # Create audit log entry for stale model
        from sqlalchemy import text
        
        query = text("""
            INSERT INTO audit_log (
                timestamp,
                model_version,
                feature_hash,
                tile_id,
                risk_score,
                confidence_p10,
                confidence_p90,
                user_id,
                action
            ) VALUES (
                :timestamp,
                :model_version,
                'N/A',
                'N/A',
                NULL,
                NULL,
                NULL,
                :user_id,
                'MODEL_STALENESS_WARNING'
            )
            RETURNING id
        """)
        
        with self.engine.begin() as conn:
            result = conn.execute(
                query,
                {
                    "timestamp": datetime.now(),
                    "model_version": staleness_check["model_id"],
                    "user_id": user_id,
                },
            )
            audit_id = result.fetchone()[0]
        
        logger.warning("Stale model: %s", staleness_check["warning"])
        logger.info("Stale model flagged in audit log (ID: %s)", audit_id)
        
        return audit_id
