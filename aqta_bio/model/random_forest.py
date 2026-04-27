"""M2 — Random Forest model for zoonotic spillover risk."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from aqta_bio.model.logistic_regression import FEATURE_COLUMNS


def train_random_forest(
    train_df: pd.DataFrame,
    sample_weights: pd.Series,
    feature_columns: list[str] = FEATURE_COLUMNS,
    n_estimators: int = 500,
    max_depth: int = 12,
    min_samples_leaf: int = 10,
    random_state: int = 42,
) -> tuple[RandomForestClassifier, dict]:
    """
    Train M2 — Random Forest.

    Args:
        train_df: DataFrame containing feature_columns plus a "label" column.
        sample_weights: Series aligned with train_df index providing per-sample weights.
        feature_columns: Ordered list of feature column names to use.
        n_estimators: Number of trees (default 500).
        max_depth: Maximum tree depth (default 12).
        min_samples_leaf: Minimum samples per leaf (default 10).
        random_state: Random seed (default 42).

    Returns:
        Tuple of (model, feature_importance_report) where feature_importance_report has:
            - "importances": dict mapping feature_name -> importance_score (sorted desc).
            - "top_5": list of (feature_name, score) for the top 5 features.
    """
    X = train_df[feature_columns].to_numpy()
    y = train_df["label"].to_numpy()
    weights = sample_weights.loc[train_df.index].to_numpy()

    model = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        class_weight="balanced_subsample",
        random_state=random_state,
    )
    model.fit(X, y, sample_weight=weights)

    importances = model.feature_importances_
    ranked = sorted(zip(feature_columns, importances), key=lambda x: x[1], reverse=True)

    feature_importance_report = {
        "importances": {name: score for name, score in ranked},
        "top_5": ranked[:5],
    }

    return model, feature_importance_report


def predict_proba(
    model: RandomForestClassifier,
    df: pd.DataFrame,
    feature_columns: list[str] = FEATURE_COLUMNS,
) -> np.ndarray:
    """
    Return predicted probabilities for the positive class.

    Args:
        model: Trained RandomForestClassifier.
        df: DataFrame containing feature_columns.
        feature_columns: Ordered list of feature column names.

    Returns:
        1-D numpy array of positive-class probabilities, shape (n_samples,).
    """
    X = df[feature_columns].to_numpy()
    return model.predict_proba(X)[:, 1]
