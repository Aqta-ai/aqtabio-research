"""
Audit logging module for governance gateway.

This module implements audit trail functionality that logs every prediction
request for accountability and compliance. All predictions are logged with
model version, feature hash, timestamp, tile_id, risk_score, and confidence bands.

Validates: Requirement 6.1
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from aqta_bio.config import get_database_url


def compute_feature_hash(features: Dict[str, Any]) -> str:
    """
    Compute SHA-256 hash of feature values for reproducibility tracking.
    
    Args:
        features: Dictionary of feature names to values
    
    Returns:
        Hexadecimal SHA-256 hash string
    """
    # Sort features by key for deterministic hashing
    sorted_features = sorted(features.items())
    
    # Create string representation of features
    feature_str = ",".join(f"{k}:{v}" for k, v in sorted_features)
    
    # Compute SHA-256 hash
    hash_obj = hashlib.sha256(feature_str.encode('utf-8'))
    return hash_obj.hexdigest()


def log_prediction_audit(
    tile_id: str,
    risk_score: float,
    confidence_p10: float,
    confidence_p90: float,
    model_version: str,
    feature_hash: str,
    user_id: str = "system",
    action: str = "predict",
    engine: Optional[Engine] = None,
) -> int:
    """
    Write an audit log entry for a prediction request.
    
    This function logs every prediction made by the system to ensure full
    accountability and traceability. The audit log captures:
    - When the prediction was made (timestamp)
    - Which model version was used (model_version)
    - What features were used (feature_hash)
    - Which tile was predicted (tile_id)
    - What the prediction was (risk_score, confidence bands)
    - Who requested it (user_id)
    - What action was performed (action)
    
    Args:
        tile_id: Tile identifier (e.g., "AF-025-12345")
        risk_score: Predicted risk score [0, 1]
        confidence_p10: 10th percentile confidence bound
        confidence_p90: 90th percentile confidence bound
        model_version: Model version identifier (SHA hash or version string)
        feature_hash: SHA-256 hash of feature set used for prediction
        user_id: User identifier (default: "system" for automated predictions)
        action: Action type (default: "predict", also: "export", "retrain")
        engine: SQLAlchemy engine (created if not provided)
    
    Returns:
        Audit log entry ID
    
    Raises:
        Exception: If database write fails
    
    Validates: Requirement 6.1
    """
    if engine is None:
        db_url = get_database_url()
        engine = create_engine(db_url)
    
    # Prepare audit entry
    timestamp = datetime.now()
    
    # Insert audit log entry
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
            :feature_hash,
            :tile_id,
            :risk_score,
            :confidence_p10,
            :confidence_p90,
            :user_id,
            :action
        )
    """)
    
    with engine.connect() as conn:
        conn.execute(
            query,
            {
                "timestamp": timestamp,
                "model_version": model_version,
                "feature_hash": feature_hash,
                "tile_id": tile_id,
                "risk_score": risk_score,
                "confidence_p10": confidence_p10,
                "confidence_p90": confidence_p90,
                "user_id": user_id,
                "action": action,
            }
        )
        conn.commit()
    
    return 0


def log_export_audit(
    tile_ids: list[str],
    model_version: str,
    user_id: str,
    export_format: str,
    engine: Optional[Engine] = None,
) -> list[int]:
    """
    Write audit log entries for data export requests.
    
    Logs each tile included in an export for full traceability of data access.
    
    Args:
        tile_ids: List of tile identifiers being exported
        model_version: Model version used for predictions
        user_id: User identifier requesting export
        export_format: Export format (e.g., "csv", "geojson")
        engine: SQLAlchemy engine (created if not provided)
    
    Returns:
        List of audit log entry IDs
    
    Validates: Requirement 6.1
    """
    if engine is None:
        db_url = get_database_url()
        engine = create_engine(db_url)
    
    audit_ids = []
    timestamp = datetime.now()
    
    # Log each tile in the export
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
            :feature_hash,
            :tile_id,
            NULL,
            NULL,
            NULL,
            :user_id,
            :action
        )
        RETURNING id
    """)
    
    with engine.connect() as conn:
        for tile_id in tile_ids:
            result = conn.execute(
                query,
                {
                    "timestamp": timestamp,
                    "model_version": model_version,
                    "feature_hash": f"export_{export_format}",
                    "tile_id": tile_id,
                    "user_id": user_id,
                    "action": "export",
                }
            )
            audit_ids.append(result.scalar())
        
        conn.commit()
    
    return audit_ids


def log_layer_view_audit(
    layer_id: str,
    user_id: str,
    enabled: bool,
    engine: Optional[Engine] = None,
) -> int:
    """
    Log a data-layer toggle event for the audit trail (pilot-ready slice).

    Stores layer_id and on/off state so that "which layers were viewed, when, by whom"
    is fully auditable. Uses action='layer_toggle'; feature_hash=layer_id;
    model_version='enabled' or 'disabled'.

    Args:
        layer_id: Data layer identifier (e.g. 'wildlife', 'environmental-stress').
        user_id: User identifier (or 'anonymous' if unauthenticated).
        enabled: True if layer was turned on, False if turned off.
        engine: SQLAlchemy engine (created if not provided).

    Returns:
        Audit log entry ID.
    """
    if engine is None:
        db_url = get_database_url()
        engine = create_engine(db_url)

    timestamp = datetime.now()
    state = "enabled" if enabled else "disabled"

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
            :feature_hash,
            NULL,
            NULL,
            NULL,
            NULL,
            :user_id,
            'layer_toggle'
        )
        RETURNING id
    """)

    with engine.connect() as conn:
        result = conn.execute(
            query,
            {
                "timestamp": timestamp,
                "model_version": state,
                "feature_hash": layer_id,
                "user_id": user_id,
            },
        )
        audit_id = result.scalar()
        conn.commit()

    return audit_id


def query_audit_log(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    tile_id: Optional[str] = None,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    model_version: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    engine: Optional[Engine] = None,
) -> list[Dict[str, Any]]:
    """
    Query audit log entries with filters.
    
    Args:
        start_date: Filter entries after this date (inclusive)
        end_date: Filter entries before this date (inclusive)
        tile_id: Filter by tile identifier
        user_id: Filter by user identifier
        action: Filter by action type
        model_version: Filter by model version
        limit: Maximum number of results
        offset: Pagination offset
        engine: SQLAlchemy engine (created if not provided)
    
    Returns:
        List of audit log entries as dictionaries
    """
    if engine is None:
        db_url = get_database_url()
        engine = create_engine(db_url)
    
    # Build WHERE clauses
    where_clauses = []
    params = {"limit": limit, "offset": offset}
    
    if start_date:
        where_clauses.append("timestamp >= :start_date")
        params["start_date"] = start_date
    
    if end_date:
        where_clauses.append("timestamp <= :end_date")
        params["end_date"] = end_date
    
    if tile_id:
        where_clauses.append("tile_id = :tile_id")
        params["tile_id"] = tile_id
    
    if user_id:
        where_clauses.append("user_id = :user_id")
        params["user_id"] = user_id
    
    if action:
        where_clauses.append("action = :action")
        params["action"] = action
    
    if model_version:
        where_clauses.append("model_version = :model_version")
        params["model_version"] = model_version
    
    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # Query audit log
    query = text(f"""
        SELECT
            id,
            timestamp,
            model_version,
            feature_hash,
            tile_id,
            risk_score,
            confidence_p10,
            confidence_p90,
            user_id,
            action
        FROM audit_log
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT :limit OFFSET :offset
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, params)
        rows = result.fetchall()
    
    # Convert to list of dicts
    entries = []
    for row in rows:
        entries.append({
            "id": row.id,
            "timestamp": row.timestamp.isoformat(),
            "model_version": row.model_version,
            "feature_hash": row.feature_hash,
            "tile_id": row.tile_id,
            "risk_score": row.risk_score,
            "confidence_p10": row.confidence_p10,
            "confidence_p90": row.confidence_p90,
            "user_id": row.user_id,
            "action": row.action,
        })
    
    return entries
