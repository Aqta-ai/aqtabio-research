"""
Governance Gateway module for Aqta Bio.

This module implements the 8-layer governance framework:
1. Audit logging (Task 7.1)
2. Model SHA verification (Task 7.2)
3. Circuit breaker for data staleness (Task 7.3)
4. Human-in-the-loop sign-off (Task 7.4)
5. Confidence bands (implemented in model layer)
6. RBAC (Task 7.5)
7. SHAP explanations (implemented in model layer)
8. Bias monitoring (Task 7.6)

Validates: Requirement 6 (Governance Gateway)
"""

from aqta_bio.governance.audit import (
    compute_feature_hash,
    log_prediction_audit,
    log_export_audit,
    log_layer_view_audit,
    query_audit_log,
)
from aqta_bio.governance.gateway import (
    GovernanceGateway,
    ModelIntegrityError,
    ModelVerificationResult,
    DataStalenessWarning,
)

__all__ = [
    "compute_feature_hash",
    "log_prediction_audit",
    "log_export_audit",
    "log_layer_view_audit",
    "query_audit_log",
    "GovernanceGateway",
    "ModelIntegrityError",
    "ModelVerificationResult",
    "DataStalenessWarning",
]
