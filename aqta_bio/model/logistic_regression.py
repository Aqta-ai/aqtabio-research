"""M1 — Logistic Regression baseline model for zoonotic spillover risk."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = [
    "biotic_transition_index",
    "lulc_diversity_shannon",
    "forest_loss_3yr",
    "forest_gain_reversion",
    "temp_anomaly_12mo",
    "rainfall_anomaly_12mo",
    "population_density_log",
    "livestock_density_pig_log",
    "road_density",
    "conflict_density_50km",
    "distance_to_past_spillover_log",
    "anthrome_transition_flag",
]

# Expected biological sign for each feature (positive = increases risk)
EXPECTED_SIGNS = {
    "biotic_transition_index": +1,
    "lulc_diversity_shannon": +1,
    "forest_loss_3yr": +1,
    "forest_gain_reversion": +1,
    "temp_anomaly_12mo": +1,
    "rainfall_anomaly_12mo": +1,
    "population_density_log": +1,
    "livestock_density_pig_log": +1,
    "road_density": +1,
    "conflict_density_50km": +1,
    "distance_to_past_spillover_log": -1,  # farther = lower risk
    "anthrome_transition_flag": +1,
}


def train_logistic_regression(
    train_df: pd.DataFrame,
    sample_weights: pd.Series,
    feature_columns: list[str] = FEATURE_COLUMNS,
    C: float = 0.1,
    max_iter: int = 500,
) -> tuple[LogisticRegression, StandardScaler, dict]:
    """Train M1 — Logistic Regression baseline.

    Scales features with StandardScaler, trains a balanced logistic regression,
    and performs a coefficient sign check against biological expectations.

    Args:
        train_df: DataFrame containing feature_columns plus a "label" column.
        sample_weights: Series aligned with train_df index providing per-sample weights.
        feature_columns: Ordered list of feature column names to use.
        C: Inverse regularisation strength (default 0.1).
        max_iter: Maximum solver iterations (default 500).

    Returns:
        A tuple of (model, scaler, sign_check_report) where sign_check_report has:
            - "passed": bool — True if all coefficient signs match EXPECTED_SIGNS.
            - "violations": list of dicts with keys "feature", "expected", "actual".
    """
    X = train_df[feature_columns].to_numpy()
    y = train_df["label"].to_numpy()
    weights = sample_weights.loc[train_df.index].to_numpy()

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LogisticRegression(
        C=C,
        class_weight="balanced",
        max_iter=max_iter,
        solver="lbfgs",
    )
    model.fit(X_scaled, y, sample_weight=weights)

    # Coefficient sign check
    coefs = model.coef_[0]
    violations = []
    for i, feature in enumerate(feature_columns):
        expected = EXPECTED_SIGNS.get(feature)
        if expected is None:
            continue
        actual_sign = int(np.sign(coefs[i]))
        if actual_sign != expected:
            violations.append(
                {"feature": feature, "expected": expected, "actual": actual_sign}
            )

    sign_check_report = {
        "passed": len(violations) == 0,
        "violations": violations,
    }

    return model, scaler, sign_check_report


def predict_proba(
    model: LogisticRegression,
    scaler: StandardScaler,
    df: pd.DataFrame,
    feature_columns: list[str] = FEATURE_COLUMNS,
) -> np.ndarray:
    """Return predicted probabilities for the positive class.

    Args:
        model: Trained LogisticRegression model.
        scaler: Fitted StandardScaler used during training.
        df: DataFrame containing feature_columns.
        feature_columns: Ordered list of feature column names.

    Returns:
        1-D numpy array of positive-class probabilities, shape (n_samples,).
    """
    X = df[feature_columns].to_numpy()
    X_scaled = scaler.transform(X)
    return model.predict_proba(X_scaled)[:, 1]
