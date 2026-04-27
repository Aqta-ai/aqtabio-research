"""M3 — XGBoost primary model for zoonotic spillover risk with quantile regression."""

from __future__ import annotations

import numpy as np
import pandas as pd
import xgboost as xgb

from aqta_bio.model.logistic_regression import FEATURE_COLUMNS


def train_xgboost(
    train_df: pd.DataFrame,
    sample_weights: pd.Series,
    feature_columns: list[str] = FEATURE_COLUMNS,
    n_estimators: int = 1000,
    learning_rate: float = 0.05,
    max_depth: int = 7,
    subsample: float = 0.8,
    scale_pos_weight: float = 10.0,
    early_stopping_rounds: int = 50,
    random_state: int = 42,
    eval_set: tuple[pd.DataFrame, pd.Series] | None = None,
) -> tuple[xgb.XGBClassifier, dict]:
    """
    Train M3 — XGBoost primary model.

    Args:
        train_df: DataFrame containing feature_columns plus a "label" column.
        sample_weights: Series aligned with train_df index providing per-sample weights.
        feature_columns: Ordered list of feature column names to use.
        n_estimators: Number of boosting rounds (default 1000).
        learning_rate: Step size shrinkage (default 0.05).
        max_depth: Maximum tree depth (default 7).
        subsample: Subsample ratio of training instances (default 0.8).
        scale_pos_weight: Balancing of positive and negative weights (default 10.0).
        early_stopping_rounds: Activates early stopping (default 50).
        random_state: Random seed (default 42).
        eval_set: Optional tuple of (X_val, y_val) for early stopping validation.

    Returns:
        Tuple of (model, training_report) where training_report has:
            - "best_iteration": int — best boosting round (if early stopping used).
            - "best_score": float — best validation score (if early stopping used).
            - "feature_importance": dict mapping feature_name -> importance_score (sorted desc).
            - "top_5": list of (feature_name, score) for the top 5 features.
    """
    X = train_df[feature_columns].to_numpy()
    y = train_df["label"].to_numpy()
    weights = sample_weights.loc[train_df.index].to_numpy()

    # Configure early stopping if eval_set provided
    early_stopping_rounds_param = early_stopping_rounds if eval_set is not None else None
    
    model = xgb.XGBClassifier(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        subsample=subsample,
        scale_pos_weight=scale_pos_weight,
        random_state=random_state,
        eval_metric="logloss",
        use_label_encoder=False,
        early_stopping_rounds=early_stopping_rounds_param,
        base_score=0.5,  # Explicit base_score for SHAP compatibility
    )

    # Prepare eval_set for early stopping if provided
    fit_params = {"sample_weight": weights}
    if eval_set is not None:
        X_val, y_val = eval_set
        fit_params["eval_set"] = [(X_val[feature_columns].to_numpy(), y_val.to_numpy())]
        fit_params["verbose"] = False

    model.fit(X, y, **fit_params)

    # Extract feature importance
    importances = model.feature_importances_
    ranked = sorted(zip(feature_columns, importances), key=lambda x: x[1], reverse=True)

    training_report = {
        "best_iteration": getattr(model, "best_iteration", n_estimators),
        "best_score": getattr(model, "best_score", None),
        "feature_importance": {name: score for name, score in ranked},
        "top_5": ranked[:5],
    }

    return model, training_report


def train_quantile_regressors(
    train_df: pd.DataFrame,
    sample_weights: pd.Series,
    feature_columns: list[str] = FEATURE_COLUMNS,
    quantiles: list[float] = [0.1, 0.9],
    n_estimators: int = 1000,
    learning_rate: float = 0.05,
    max_depth: int = 7,
    subsample: float = 0.8,
    random_state: int = 42,
) -> dict[float, xgb.XGBRegressor]:
    """
    Train XGBoost quantile regression models for confidence bands.

    This trains separate XGBoost regressors for each quantile (10th and 90th percentile)
    to produce confidence bands around the primary classifier's predictions.

    Args:
        train_df: DataFrame containing feature_columns plus a "label" column.
        sample_weights: Series aligned with train_df index providing per-sample weights.
        feature_columns: Ordered list of feature column names to use.
        quantiles: List of quantiles to train (default [0.1, 0.9] for 10th/90th percentile).
        n_estimators: Number of boosting rounds (default 1000).
        learning_rate: Step size shrinkage (default 0.05).
        max_depth: Maximum tree depth (default 7).
        subsample: Subsample ratio of training instances (default 0.8).
        random_state: Random seed (default 42).

    Returns:
        Dictionary mapping quantile -> trained XGBRegressor model.
    """
    X = train_df[feature_columns].to_numpy()
    y = train_df["label"].to_numpy().astype(float)
    weights = sample_weights.loc[train_df.index].to_numpy()

    quantile_models = {}

    for quantile in quantiles:
        model = xgb.XGBRegressor(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            subsample=subsample,
            objective="reg:quantileerror",
            quantile_alpha=quantile,
            random_state=random_state,
        )

        model.fit(X, y, sample_weight=weights, verbose=False)
        quantile_models[quantile] = model

    return quantile_models


def predict_proba(
    model: xgb.XGBClassifier,
    df: pd.DataFrame,
    feature_columns: list[str] = FEATURE_COLUMNS,
) -> np.ndarray:
    """
    Return predicted probabilities for the positive class.

    Args:
        model: Trained XGBClassifier.
        df: DataFrame containing feature_columns.
        feature_columns: Ordered list of feature column names.

    Returns:
        1-D numpy array of positive-class probabilities, shape (n_samples,).
    """
    X = df[feature_columns].to_numpy()
    return model.predict_proba(X)[:, 1]


def predict_with_confidence_bands(
    classifier: xgb.XGBClassifier,
    quantile_models: dict[float, xgb.XGBRegressor],
    df: pd.DataFrame,
    feature_columns: list[str] = FEATURE_COLUMNS,
) -> pd.DataFrame:
    """
    Predict risk scores with confidence bands.

    Args:
        classifier: Trained XGBClassifier for primary risk prediction.
        quantile_models: Dictionary mapping quantile -> XGBRegressor for confidence bands.
        df: DataFrame containing feature_columns.
        feature_columns: Ordered list of feature column names.

    Returns:
        DataFrame with columns:
            - "risk_score": Primary prediction from classifier.
            - "p10": 10th percentile confidence bound.
            - "p90": 90th percentile confidence bound.
    """
    X = df[feature_columns].to_numpy()

    # Primary prediction
    risk_scores = classifier.predict_proba(X)[:, 1]

    # Quantile predictions
    p10 = quantile_models[0.1].predict(X) if 0.1 in quantile_models else None
    p90 = quantile_models[0.9].predict(X) if 0.9 in quantile_models else None

    # Clip quantile predictions to [0, 1] range
    if p10 is not None:
        p10 = np.clip(p10, 0.0, 1.0)
    if p90 is not None:
        p90 = np.clip(p90, 0.0, 1.0)

    result = pd.DataFrame(
        {
            "risk_score": risk_scores,
            "p10": p10 if p10 is not None else risk_scores,
            "p90": p90 if p90 is not None else risk_scores,
        },
        index=df.index,
    )

    return result
