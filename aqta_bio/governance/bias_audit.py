"""
Bias Audit module for monitoring fairness across income groups.

This module implements Requirement 6.8:
"WHEN a quarterly bias audit runs, THE Governance_Gateway SHALL compute recall
across LIC, LMIC, and HIC tile groups and flag any recall gap exceeding
15 percentage points."

The bias audit ensures that the model performs equitably across countries
with different income levels, preventing systematic underperformance in
low-income regions where spillover risk may be highest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class BiasReport:
    """
    Result of a bias audit across income groups.
    
    Attributes:
        lic_recall: Recall for Low Income Countries
        lmic_recall: Recall for Lower-Middle Income Countries
        hic_recall: Recall for High Income Countries
        max_gap: Maximum recall gap between any two groups (percentage points)
        flagged: True if max_gap > threshold
        threshold: Threshold used for flagging (default: 15 percentage points)
        message: Human-readable summary of audit results
        tile_counts: Dictionary with tile counts per income group
    """
    lic_recall: float
    lmic_recall: float
    hic_recall: float
    max_gap: float
    flagged: bool
    threshold: float
    message: str
    tile_counts: dict[str, int]
    
    def __str__(self) -> str:
        """Return human-readable summary."""
        return self.message


def run_bias_audit(
    predictions: pd.DataFrame,
    tile_income_groups: pd.Series,
    threshold: float = 15.0,
) -> BiasReport:
    """
    Compute recall across LIC/LMIC/HIC tile groups and flag disparities.
    
    This function implements Requirement 6.8:
    "WHEN a quarterly bias audit runs, THE Governance_Gateway SHALL compute recall
    across LIC, LMIC, and HIC tile groups and flag any recall gap exceeding
    15 percentage points."
    
    Recall is computed as: TP / (TP + FN) for each income group.
    A gap is flagged if the difference between the highest and lowest recall
    exceeds the threshold (default: 15 percentage points).
    
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
    
    Raises:
        ValueError: If required columns are missing or income groups are invalid
    
    Validates: Requirement 6.8
    
    Example:
        >>> predictions = pd.DataFrame({
        ...     'tile_id': ['AF-025-001', 'AF-025-002', 'AF-025-003'],
        ...     'y_true': [1, 1, 0],
        ...     'y_pred': [1, 0, 0]
        ... })
        >>> income_groups = pd.Series({
        ...     'AF-025-001': 'LIC',
        ...     'AF-025-002': 'LMIC',
        ...     'AF-025-003': 'HIC'
        ... })
        >>> report = run_bias_audit(predictions, income_groups)
        >>> print(report.message)
    """
    # Validate inputs
    required_cols = {'tile_id', 'y_true', 'y_pred'}
    if not required_cols.issubset(predictions.columns):
        missing = required_cols - set(predictions.columns)
        raise ValueError(
            f"predictions DataFrame missing required columns: {missing}"
        )
    
    # Merge predictions with income groups
    df = predictions.copy()
    df['income_group'] = df['tile_id'].map(tile_income_groups)
    
    # Remove tiles without income group mapping
    df = df.dropna(subset=['income_group'])
    
    if len(df) == 0:
        raise ValueError("No tiles with valid income group mappings")
    
    # Validate income groups
    valid_groups = {'LIC', 'LMIC', 'HIC'}
    invalid_groups = set(df['income_group'].unique()) - valid_groups
    if invalid_groups:
        raise ValueError(
            f"Invalid income groups found: {invalid_groups}. "
            f"Valid groups are: {valid_groups}"
        )
    
    # Compute recall for each income group
    recalls = {}
    tile_counts = {}
    
    for group in ['LIC', 'LMIC', 'HIC']:
        group_df = df[df['income_group'] == group]
        tile_counts[group] = len(group_df)
        
        if len(group_df) == 0:
            # No tiles in this group
            recalls[group] = 0.0
            continue
        
        # Compute recall: TP / (TP + FN)
        true_positives = ((group_df['y_true'] == 1) & (group_df['y_pred'] == 1)).sum()
        false_negatives = ((group_df['y_true'] == 1) & (group_df['y_pred'] == 0)).sum()
        
        total_positives = true_positives + false_negatives
        
        if total_positives == 0:
            # No positive samples in this group
            recalls[group] = 0.0
        else:
            recalls[group] = true_positives / total_positives
    
    lic_recall = recalls['LIC']
    lmic_recall = recalls['LMIC']
    hic_recall = recalls['HIC']
    
    # Compute maximum gap (in percentage points)
    recall_values = [lic_recall, lmic_recall, hic_recall]
    max_recall = max(recall_values)
    min_recall = min(recall_values)
    max_gap = (max_recall - min_recall) * 100  # Convert to percentage points
    
    # Flag if gap exceeds threshold
    flagged = max_gap > threshold
    
    # Generate message
    if flagged:
        message = (
            f"⚠ BIAS ALERT: Recall gap of {max_gap:.1f} percentage points "
            f"exceeds threshold of {threshold:.1f}pp. "
            f"LIC: {lic_recall*100:.1f}%, LMIC: {lmic_recall*100:.1f}%, "
            f"HIC: {hic_recall*100:.1f}%. "
            f"Model may be underperforming in certain income groups."
        )
    else:
        message = (
            f"✓ Bias audit passed. Recall gap of {max_gap:.1f} percentage points "
            f"is within threshold of {threshold:.1f}pp. "
            f"LIC: {lic_recall*100:.1f}%, LMIC: {lmic_recall*100:.1f}%, "
            f"HIC: {hic_recall*100:.1f}%."
        )
    
    return BiasReport(
        lic_recall=lic_recall,
        lmic_recall=lmic_recall,
        hic_recall=hic_recall,
        max_gap=max_gap,
        flagged=flagged,
        threshold=threshold,
        message=message,
        tile_counts=tile_counts,
    )
