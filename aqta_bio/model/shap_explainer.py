"""SHAP explainer for XGBoost model interpretability.

This module implements SHAP (SHapley Additive exPlanations) value computation
for the M3 XGBoost model, providing per-tile, per-month feature importance
explanations as required by Requirement 4.6.

SHAP values explain individual predictions by quantifying each feature's
contribution to moving the prediction away from the base value (average prediction).
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd
import shap
import xgboost as xgb

from aqta_bio.model.logistic_regression import FEATURE_COLUMNS


def compute_shap_values(
    model: xgb.XGBClassifier,
    X: pd.DataFrame,
    feature_columns: List[str] = FEATURE_COLUMNS,
) -> np.ndarray:
    """
    Compute SHAP values for all samples in X.

    Args:
        model: Trained XGBClassifier.
        X: DataFrame containing feature_columns.
        feature_columns: Ordered list of feature column names.

    Returns:
        2-D numpy array of SHAP values, shape (n_samples, n_features).
        Each row contains SHAP values for one sample, one value per feature.
    """
    # Extract feature matrix
    X_features = X[feature_columns].to_numpy()

    # Create TreeExplainer for XGBoost
    # Use model_output='raw' to avoid base_score parsing issues with XGBoost 2.x
    explainer = shap.TreeExplainer(model, model_output='raw')

    # Compute SHAP values
    # For binary classification, shap_values returns values for positive class
    shap_values = explainer.shap_values(X_features)

    return shap_values


def extract_top_drivers(
    shap_values: np.ndarray,
    feature_columns: List[str] = FEATURE_COLUMNS,
    top_k: int = 3,
) -> pd.DataFrame:
    """
    Extract top K contributing features per sample based on absolute SHAP values.

    Args:
        shap_values: 2-D array of SHAP values, shape (n_samples, n_features).
        feature_columns: Ordered list of feature column names.
        top_k: Number of top drivers to extract per sample (default 3).

    Returns:
        DataFrame with columns:
            - "sample_idx": Sample index.
            - "rank": Rank of driver (1 = most important).
            - "feature_name": Name of the feature.
            - "shap_value": SHAP value for this feature.
            - "abs_shap_value": Absolute SHAP value (used for ranking).
    """
    n_samples, n_features = shap_values.shape
    assert len(feature_columns) == n_features, "Feature columns must match SHAP values"

    records = []

    for sample_idx in range(n_samples):
        # Get SHAP values for this sample
        sample_shap = shap_values[sample_idx, :]

        # Rank features by absolute SHAP value (descending)
        abs_shap = np.abs(sample_shap)
        top_indices = np.argsort(abs_shap)[::-1][:top_k]

        for rank, feature_idx in enumerate(top_indices, start=1):
            records.append({
                "sample_idx": sample_idx,
                "rank": rank,
                "feature_name": feature_columns[feature_idx],
                "shap_value": sample_shap[feature_idx],
                "abs_shap_value": abs_shap[feature_idx],
            })

    return pd.DataFrame(records)


def compute_shap_explanations(
    model: xgb.XGBClassifier,
    X: pd.DataFrame,
    feature_columns: List[str] = FEATURE_COLUMNS,
    top_k: int = 3,
) -> pd.DataFrame:
    """
    Compute SHAP explanations and extract top K drivers per sample.

    This is the main entry point for SHAP explanation generation, combining
    SHAP value computation and top driver extraction.

    Args:
        model: Trained XGBClassifier.
        X: DataFrame containing feature_columns.
        feature_columns: Ordered list of feature column names.
        top_k: Number of top drivers to extract per sample (default 3).

    Returns:
        DataFrame with top K drivers per sample, containing:
            - "sample_idx": Sample index (matches X.index).
            - "rank": Rank of driver (1 = most important).
            - "feature_name": Name of the feature.
            - "shap_value": SHAP value for this feature.
            - "abs_shap_value": Absolute SHAP value (used for ranking).

    Example:
        >>> model, _ = train_xgboost(train_df, sample_weights)
        >>> explanations = compute_shap_explanations(model, test_df, top_k=3)
        >>> # Get top 3 drivers for first sample
        >>> sample_0_drivers = explanations[explanations["sample_idx"] == 0]
    """
    # Compute SHAP values
    shap_values = compute_shap_values(model, X, feature_columns)

    # Extract top drivers
    top_drivers_df = extract_top_drivers(shap_values, feature_columns, top_k)

    return top_drivers_df


def get_top_drivers_for_tile(
    explanations_df: pd.DataFrame,
    sample_idx: int,
    top_k: int = 3,
) -> List[Tuple[str, float]]:
    """
    Get top K drivers for a specific tile (sample).

    Args:
        explanations_df: DataFrame from compute_shap_explanations.
        sample_idx: Index of the sample/tile.
        top_k: Number of top drivers to return (default 3).

    Returns:
        List of (feature_name, shap_value) tuples, sorted by absolute SHAP value.

    Example:
        >>> explanations = compute_shap_explanations(model, test_df)
        >>> top_3 = get_top_drivers_for_tile(explanations, sample_idx=0)
        >>> print(top_3)
        [('forest_loss_3yr', 0.18), ('biotic_transition_index', 0.12), ...]
    """
    tile_drivers = explanations_df[explanations_df["sample_idx"] == sample_idx]
    tile_drivers = tile_drivers.sort_values("rank").head(top_k)

    return list(zip(tile_drivers["feature_name"], tile_drivers["shap_value"]))


def compute_global_feature_importance(
    shap_values: np.ndarray,
    feature_columns: List[str] = FEATURE_COLUMNS,
) -> pd.DataFrame:
    """
    Compute global feature importance by averaging absolute SHAP values.

    This provides a model-level view of which features are most important
    across all predictions, complementing per-tile explanations.

    Args:
        shap_values: 2-D array of SHAP values, shape (n_samples, n_features).
        feature_columns: Ordered list of feature column names.

    Returns:
        DataFrame with columns:
            - "feature_name": Name of the feature.
            - "mean_abs_shap": Mean absolute SHAP value across all samples.
            - "rank": Rank by importance (1 = most important).

        Sorted by mean_abs_shap descending.
    """
    # Compute mean absolute SHAP value per feature
    mean_abs_shap = np.mean(np.abs(shap_values), axis=0)

    # Create DataFrame
    importance_df = pd.DataFrame({
        "feature_name": feature_columns,
        "mean_abs_shap": mean_abs_shap,
    })

    # Sort by importance and add rank
    importance_df = importance_df.sort_values("mean_abs_shap", ascending=False)
    importance_df["rank"] = range(1, len(importance_df) + 1)

    return importance_df.reset_index(drop=True)


def format_shap_drivers_for_api(
    explanations_df: pd.DataFrame,
    sample_idx: int,
    top_k: int = 3,
) -> List[dict]:
    """
    Format SHAP drivers for API response.

    Converts SHAP explanations to the format expected by the FastAPI backend
    (matching the SHAPDriver Pydantic model).

    Args:
        explanations_df: DataFrame from compute_shap_explanations.
        sample_idx: Index of the sample/tile.
        top_k: Number of top drivers to return (default 3).

    Returns:
        List of dicts with keys:
            - "feature_name": str
            - "shap_value": float

    Example:
        >>> explanations = compute_shap_explanations(model, test_df)
        >>> api_drivers = format_shap_drivers_for_api(explanations, sample_idx=0)
        >>> # Returns: [{"feature_name": "forest_loss_3yr", "shap_value": 0.18}, ...]
    """
    tile_drivers = explanations_df[explanations_df["sample_idx"] == sample_idx]
    tile_drivers = tile_drivers.sort_values("rank").head(top_k)

    return [
        {
            "feature_name": row["feature_name"],
            "shap_value": float(row["shap_value"]),
        }
        for _, row in tile_drivers.iterrows()
    ]
