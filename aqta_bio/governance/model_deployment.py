"""
Model deployment tracking and retraining service.

This module implements Requirement 6.9:
"WHEN a model has been in production for more than 12 months without retraining,
THE Governance_Gateway SHALL flag the model as 'Due for retraining' in the audit
log and Dashboard. THE Model_Registry SHALL support triggered retraining via an
Admin API endpoint."

Validates: Requirement 6.9
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class ModelDeployment:
    """Model deployment record."""
    id: int
    model_id: str
    model_type: str
    pathogen_id: str
    mlflow_run_id: str
    sha_hash: str
    deployed_at: datetime
    deployed_by: str
    status: str
    last_retrained_at: Optional[datetime]
    notes: Optional[str]


@dataclass
class RetrainingRequest:
    """Model retraining request record."""
    id: int
    deployment_id: Optional[int]
    pathogen_id: str
    requested_by: str
    requested_at: datetime
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    new_model_id: Optional[str]
    new_mlflow_run_id: Optional[str]
    error_message: Optional[str]
    notes: Optional[str]


class ModelDeploymentService:
    """Service for managing model deployments and retraining."""
    
    def __init__(self, session: Session):
        """
        Initialize service.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
    
    def deploy_model(
        self,
        model_id: str,
        model_type: str,
        pathogen_id: str,
        mlflow_run_id: str,
        sha_hash: str,
        deployed_by: str = "system",
        notes: Optional[str] = None,
    ) -> ModelDeployment:
        """
        Deploy a model to production.
        
        This method:
        1. Retires any existing active models for the pathogen
        2. Creates a new deployment record with status='active'
        
        Args:
            model_id: Model identifier
            model_type: Model type ("logistic", "rf", "xgboost", "gnn")
            pathogen_id: Pathogen identifier
            mlflow_run_id: MLflow run ID
            sha_hash: Model SHA-256 hash
            deployed_by: User who deployed the model
            notes: Optional deployment notes
        
        Returns:
            ModelDeployment record
        
        Example:
            >>> service = ModelDeploymentService(session)
            >>> deployment = service.deploy_model(
            ...     model_id="ebola_xgboost_20240115",
            ...     model_type="xgboost",
            ...     pathogen_id="ebola",
            ...     mlflow_run_id="abc123",
            ...     sha_hash="def456...",
            ...     deployed_by="admin@aqta.ai"
            ... )
        """
        # Retire existing active models for this pathogen
        retire_query = text("""
            UPDATE model_deployments
            SET status = 'retired', updated_at = NOW()
            WHERE pathogen_id = :pathogen_id AND status = 'active'
        """)
        self.session.execute(retire_query, {"pathogen_id": pathogen_id})
        
        # Create new deployment
        insert_query = text("""
            INSERT INTO model_deployments (
                model_id,
                model_type,
                pathogen_id,
                mlflow_run_id,
                sha_hash,
                deployed_at,
                deployed_by,
                status,
                notes
            ) VALUES (
                :model_id,
                :model_type,
                :pathogen_id,
                :mlflow_run_id,
                :sha_hash,
                NOW(),
                :deployed_by,
                'active',
                :notes
            )
            RETURNING id, deployed_at
        """)
        
        result = self.session.execute(
            insert_query,
            {
                "model_id": model_id,
                "model_type": model_type,
                "pathogen_id": pathogen_id,
                "mlflow_run_id": mlflow_run_id,
                "sha_hash": sha_hash,
                "deployed_by": deployed_by,
                "notes": notes,
            },
        )
        row = result.fetchone()
        self.session.commit()
        
        return ModelDeployment(
            id=row[0],
            model_id=model_id,
            model_type=model_type,
            pathogen_id=pathogen_id,
            mlflow_run_id=mlflow_run_id,
            sha_hash=sha_hash,
            deployed_at=row[1],
            deployed_by=deployed_by,
            status="active",
            last_retrained_at=None,
            notes=notes,
        )
    
    def get_active_deployment(
        self,
        pathogen_id: str,
    ) -> Optional[ModelDeployment]:
        """
        Get active deployment for a pathogen.
        
        Args:
            pathogen_id: Pathogen identifier
        
        Returns:
            ModelDeployment if found, None otherwise
        """
        query = text("""
            SELECT 
                id,
                model_id,
                model_type,
                pathogen_id,
                mlflow_run_id,
                sha_hash,
                deployed_at,
                deployed_by,
                status,
                last_retrained_at,
                notes
            FROM model_deployments
            WHERE pathogen_id = :pathogen_id AND status = 'active'
            ORDER BY deployed_at DESC
            LIMIT 1
        """)
        
        result = self.session.execute(query, {"pathogen_id": pathogen_id})
        row = result.fetchone()
        
        if row is None:
            return None
        
        return ModelDeployment(
            id=row[0],
            model_id=row[1],
            model_type=row[2],
            pathogen_id=row[3],
            mlflow_run_id=row[4],
            sha_hash=row[5],
            deployed_at=row[6],
            deployed_by=row[7],
            status=row[8],
            last_retrained_at=row[9],
            notes=row[10],
        )
    
    def create_retraining_request(
        self,
        pathogen_id: str,
        requested_by: str,
        deployment_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> RetrainingRequest:
        """
        Create a retraining request for a pathogen.
        
        Args:
            pathogen_id: Pathogen identifier
            requested_by: User requesting retraining
            deployment_id: Optional deployment ID to retrain
            notes: Optional request notes
        
        Returns:
            RetrainingRequest record
        
        Example:
            >>> service = ModelDeploymentService(session)
            >>> request = service.create_retraining_request(
            ...     pathogen_id="ebola",
            ...     requested_by="admin@aqta.ai",
            ...     notes="Model is 13 months old"
            ... )
        """
        insert_query = text("""
            INSERT INTO model_retraining_requests (
                deployment_id,
                pathogen_id,
                requested_by,
                requested_at,
                status,
                notes
            ) VALUES (
                :deployment_id,
                :pathogen_id,
                :requested_by,
                NOW(),
                'pending',
                :notes
            )
            RETURNING id, requested_at
        """)
        
        result = self.session.execute(
            insert_query,
            {
                "deployment_id": deployment_id,
                "pathogen_id": pathogen_id,
                "requested_by": requested_by,
                "notes": notes,
            },
        )
        row = result.fetchone()
        self.session.commit()
        
        return RetrainingRequest(
            id=row[0],
            deployment_id=deployment_id,
            pathogen_id=pathogen_id,
            requested_by=requested_by,
            requested_at=row[1],
            status="pending",
            started_at=None,
            completed_at=None,
            new_model_id=None,
            new_mlflow_run_id=None,
            error_message=None,
            notes=notes,
        )
    
    def update_retraining_status(
        self,
        request_id: int,
        status: str,
        new_model_id: Optional[str] = None,
        new_mlflow_run_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update retraining request status.
        
        Args:
            request_id: Retraining request ID
            status: New status ("in_progress", "completed", "failed")
            new_model_id: New model ID (for completed status)
            new_mlflow_run_id: New MLflow run ID (for completed status)
            error_message: Error message (for failed status)
        """
        update_query = text("""
            UPDATE model_retraining_requests
            SET 
                status = :status,
                started_at = CASE 
                    WHEN :status = 'in_progress' AND started_at IS NULL 
                    THEN NOW() 
                    ELSE started_at 
                END,
                completed_at = CASE 
                    WHEN :status IN ('completed', 'failed') 
                    THEN NOW() 
                    ELSE completed_at 
                END,
                new_model_id = :new_model_id,
                new_mlflow_run_id = :new_mlflow_run_id,
                error_message = :error_message,
                updated_at = NOW()
            WHERE id = :request_id
        """)
        
        self.session.execute(
            update_query,
            {
                "request_id": request_id,
                "status": status,
                "new_model_id": new_model_id,
                "new_mlflow_run_id": new_mlflow_run_id,
                "error_message": error_message,
            },
        )
        self.session.commit()
    
    def mark_deployment_retrained(
        self,
        deployment_id: int,
    ) -> None:
        """
        Mark a deployment as retrained.
        
        Args:
            deployment_id: Deployment ID
        """
        update_query = text("""
            UPDATE model_deployments
            SET last_retrained_at = NOW(), updated_at = NOW()
            WHERE id = :deployment_id
        """)
        
        self.session.execute(update_query, {"deployment_id": deployment_id})
        self.session.commit()
    
    def get_retraining_request(
        self,
        request_id: int,
    ) -> Optional[RetrainingRequest]:
        """
        Get retraining request by ID.
        
        Args:
            request_id: Request ID
        
        Returns:
            RetrainingRequest if found, None otherwise
        """
        query = text("""
            SELECT 
                id,
                deployment_id,
                pathogen_id,
                requested_by,
                requested_at,
                status,
                started_at,
                completed_at,
                new_model_id,
                new_mlflow_run_id,
                error_message,
                notes
            FROM model_retraining_requests
            WHERE id = :request_id
        """)
        
        result = self.session.execute(query, {"request_id": request_id})
        row = result.fetchone()
        
        if row is None:
            return None
        
        return RetrainingRequest(
            id=row[0],
            deployment_id=row[1],
            pathogen_id=row[2],
            requested_by=row[3],
            requested_at=row[4],
            status=row[5],
            started_at=row[6],
            completed_at=row[7],
            new_model_id=row[8],
            new_mlflow_run_id=row[9],
            error_message=row[10],
            notes=row[11],
        )
