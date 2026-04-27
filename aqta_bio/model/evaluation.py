"""Model evaluation module with comprehensive metrics.

This module implements the full evaluation suite required by Requirement 4.3:
- AUROC (Area Under ROC Curve)
- AUCPR (Area Under Precision-Recall Curve)
- Sensitivity at top-5% risk tiles
- Spatial coverage (% countries with at least 1 TP in top decile)
- Temporal lead time
- Spatial leave-one-region-out cross-validation
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_recall_curve,
    roc_curve,
)


@dataclass
class EvalMetrics:
    """Evaluation metrics for a trained model.
    
    Matches the design spec from design.md and validates Requirement 4.3.
    """
    auroc: float
    aucpr: float
    sensitivity_top5pct: float
    spatial_coverage: float  # % countries with TP in top decile
    temporal_lead_time: float  # months
    
    # Additional diagnostic metrics
    precision_at_top5pct: Optional[float] = None
    recall_at_top5pct: Optional[float] = None
    n_positives: Optional[int] = None
    n_negatives: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            "auroc": float(self.auroc),
            "aucpr": float(self.aucpr),
            "sensitivity_top5pct": float(self.sensitivity_top5pct),
            "spatial_coverage": float(self.spatial_coverage),
            "temporal_lead_time": float(self.temporal_lead_time),
            "precision_at_top5pct": float(self.precision_at_top5pct) if self.precision_at_top5pct is not None else None,
            "recall_at_top5pct": float(self.recall_at_top5pct) if self.recall_at_top5pct is not None else None,
            "n_positives": int(self.n_positives) if self.n_positives is not None else None,
            "n_negatives": int(self.n_negatives) if self.n_negatives is not None else None,
        }


def compute_auroc(y_true: np.ndarray, y_pred_proba: np.ndarray) -> float:
    """Compute Area Under ROC Curve.
    
    Args:
        y_true: True binary labels (0 or 1)
        y_pred_proba: Predicted probabilities for positive class
        
    Returns:
        AUROC score in [0, 1]
    """
    if len(np.unique(y_true)) < 2:
        # Only one class present, AUROC is undefined
        return np.nan
    
    return roc_auc_score(y_true, y_pred_proba)


def compute_aucpr(y_true: np.ndarray, y_pred_proba: np.ndarray) -> float:
    """Compute Area Under Precision-Recall Curve.
    
    Args:
        y_true: True binary labels (0 or 1)
        y_pred_proba: Predicted probabilities for positive class
        
    Returns:
        AUCPR score in [0, 1]
    """
    if len(np.unique(y_true)) < 2:
        # Only one class present, AUCPR is undefined
        return np.nan
    
    return average_precision_score(y_true, y_pred_proba)


def compute_sensitivity_at_top_k_percent(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    k_percent: float = 5.0,
) -> Tuple[float, float, float]:
    """Compute sensitivity (recall) at top k% of predicted risk tiles.
    
    This metric answers: "If we focus resources on the top k% highest-risk tiles,
    what percentage of actual spillover events would we catch?"
    
    Args:
        y_true: True binary labels (0 or 1)
        y_pred_proba: Predicted probabilities for positive class
        k_percent: Percentage of top tiles to consider (default 5%)
        
    Returns:
        Tuple of (sensitivity, precision, recall) at top k%
    """
    # Sort by predicted probability (descending)
    sorted_indices = np.argsort(y_pred_proba)[::-1]
    
    # Select top k%
    n_top_k = max(1, int(len(y_pred_proba) * k_percent / 100))
    top_k_indices = sorted_indices[:n_top_k]
    
    # Get true labels for top k%
    y_true_top_k = y_true[top_k_indices]
    
    # Compute metrics
    n_true_positives = np.sum(y_true_top_k)
    n_total_positives = np.sum(y_true)
    
    sensitivity = n_true_positives / n_total_positives if n_total_positives > 0 else 0.0
    precision = n_true_positives / n_top_k if n_top_k > 0 else 0.0
    recall = sensitivity  # Sensitivity and recall are the same
    
    return sensitivity, precision, recall


def compute_spatial_coverage(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    country_codes: np.ndarray,
    top_decile: bool = True,
) -> float:
    """Compute spatial coverage: % countries with at least 1 TP in top decile.
    
    This metric measures geographic generalization: does the model identify
    high-risk tiles across multiple countries, or does it concentrate predictions
    in just a few regions?
    
    Args:
        y_true: True binary labels (0 or 1)
        y_pred_proba: Predicted probabilities for positive class
        country_codes: Country ISO3 codes for each sample
        top_decile: If True, use top 10% of predictions; if False, use top 5%
        
    Returns:
        Percentage of countries (with at least 1 positive) that have at least
        1 true positive in the top decile/5% of predictions
    """
    # Determine threshold for top decile/5%
    percentile = 90 if top_decile else 95
    threshold = np.percentile(y_pred_proba, percentile)
    
    # Identify top tiles
    top_tiles_mask = y_pred_proba >= threshold
    
    # Get countries with at least one positive sample
    countries_with_positives = set(country_codes[y_true == 1])
    
    if len(countries_with_positives) == 0:
        return 0.0
    
    # For each country with positives, check if it has at least 1 TP in top tiles
    countries_with_tp_in_top = set()
    
    for country in countries_with_positives:
        country_mask = country_codes == country
        country_top_mask = country_mask & top_tiles_mask
        country_top_positives = y_true[country_top_mask]
        
        if len(country_top_positives) > 0 and np.sum(country_top_positives) > 0:
            countries_with_tp_in_top.add(country)
    
    coverage = len(countries_with_tp_in_top) / len(countries_with_positives)
    return coverage


def compute_temporal_lead_time(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    event_dates: pd.Series,
    prediction_dates: pd.Series,
) -> float:
    """Compute average temporal lead time for true positives in top predictions.
    
    This metric measures: "How many months in advance does the model predict
    spillover events that actually occur?"
    
    Args:
        y_true: True binary labels (0 or 1)
        y_pred_proba: Predicted probabilities for positive class
        event_dates: Dates of actual spillover events (for positives)
        prediction_dates: Dates when predictions were made
        
    Returns:
        Average lead time in months for true positives in top 10% of predictions
    """
    # Get top 10% of predictions
    threshold = np.percentile(y_pred_proba, 90)
    top_tiles_mask = y_pred_proba >= threshold
    
    # Get true positives in top tiles
    tp_mask = top_tiles_mask & (y_true == 1)
    
    if np.sum(tp_mask) == 0:
        return 0.0
    
    # Compute lead times for true positives
    tp_event_dates = event_dates[tp_mask]
    tp_prediction_dates = prediction_dates[tp_mask]
    
    # Convert to datetime if not already
    if not isinstance(tp_event_dates.iloc[0], pd.Timestamp):
        tp_event_dates = pd.to_datetime(tp_event_dates)
    if not isinstance(tp_prediction_dates.iloc[0], pd.Timestamp):
        tp_prediction_dates = pd.to_datetime(tp_prediction_dates)
    
    # Compute lead time in months
    lead_times = (tp_event_dates - tp_prediction_dates).dt.days / 30.44  # Average days per month
    
    # Return average lead time
    avg_lead_time = lead_times.mean()
    
    return avg_lead_time


def evaluate_model(
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    country_codes: Optional[pd.Series] = None,
    event_dates: Optional[pd.Series] = None,
    prediction_dates: Optional[pd.Series] = None,
    feature_columns: Optional[List[str]] = None,
) -> EvalMetrics:
    """Evaluate a trained model with the full metric suite.
    
    Implements Requirement 4.3: Compute AUROC, AUCPR, sensitivity at top-5%,
    spatial coverage, and temporal lead time.
    
    Args:
        model: Trained model with predict_proba method
        X_test: Test features
        y_test: Test labels
        country_codes: Country ISO3 codes for spatial coverage (optional)
        event_dates: Event dates for temporal lead time (optional)
        prediction_dates: Prediction dates for temporal lead time (optional)
        feature_columns: List of feature column names (optional)
        
    Returns:
        EvalMetrics object with all computed metrics
    """
    # Get predictions
    if feature_columns is not None:
        X_test_features = X_test[feature_columns]
    else:
        X_test_features = X_test
    
    # Handle different model types
    if hasattr(model, 'predict_proba'):
        y_pred_proba = model.predict_proba(X_test_features)
        if y_pred_proba.ndim == 2:
            y_pred_proba = y_pred_proba[:, 1]  # Get positive class probabilities
    else:
        raise ValueError("Model must have predict_proba method")
    
    # Convert to numpy arrays
    y_true = y_test.to_numpy() if isinstance(y_test, pd.Series) else y_test
    
    # Compute core metrics
    auroc = compute_auroc(y_true, y_pred_proba)
    aucpr = compute_aucpr(y_true, y_pred_proba)
    
    # Compute sensitivity at top 5%
    sensitivity_top5pct, precision_top5pct, recall_top5pct = compute_sensitivity_at_top_k_percent(
        y_true, y_pred_proba, k_percent=5.0
    )
    
    # Compute spatial coverage if country codes provided
    if country_codes is not None:
        country_array = country_codes.to_numpy() if isinstance(country_codes, pd.Series) else country_codes
        spatial_coverage = compute_spatial_coverage(y_true, y_pred_proba, country_array)
    else:
        spatial_coverage = np.nan
    
    # Compute temporal lead time if dates provided
    if event_dates is not None and prediction_dates is not None:
        temporal_lead_time = compute_temporal_lead_time(
            y_true, y_pred_proba, event_dates, prediction_dates
        )
    else:
        temporal_lead_time = np.nan
    
    # Create metrics object
    metrics = EvalMetrics(
        auroc=auroc,
        aucpr=aucpr,
        sensitivity_top5pct=sensitivity_top5pct,
        spatial_coverage=spatial_coverage,
        temporal_lead_time=temporal_lead_time,
        precision_at_top5pct=precision_top5pct,
        recall_at_top5pct=recall_top5pct,
        n_positives=int(np.sum(y_true)),
        n_negatives=int(len(y_true) - np.sum(y_true)),
    )
    
    return metrics


def evaluate_with_spatial_cv(
    model_class: Any,
    X: pd.DataFrame,
    y: pd.Series,
    cv_folds: List[Tuple[np.ndarray, np.ndarray]],
    sample_weights: Optional[pd.Series] = None,
    feature_columns: Optional[List[str]] = None,
    **model_kwargs,
) -> List[EvalMetrics]:
    """Evaluate model using spatial cross-validation folds.
    
    Args:
        model_class: Model class or training function
        X: Full feature matrix
        y: Full labels
        cv_folds: List of (train_indices, test_indices) tuples
        sample_weights: Sample weights (optional)
        feature_columns: List of feature column names (optional)
        **model_kwargs: Additional arguments to pass to model training
        
    Returns:
        List of EvalMetrics, one per fold
    """
    fold_metrics = []
    
    for fold_idx, (train_indices, test_indices) in enumerate(cv_folds):
        # Split data
        X_train_fold = X.iloc[train_indices]
        X_test_fold = X.iloc[test_indices]
        y_train_fold = y.iloc[train_indices]
        y_test_fold = y.iloc[test_indices]
        
        if sample_weights is not None:
            weights_fold = sample_weights.iloc[train_indices]
        else:
            weights_fold = None
        
        # Train model
        # Note: This assumes model_class is a training function that returns (model, report)
        # Adjust based on actual model training interface
        if callable(model_class):
            model, _ = model_class(
                train_df=X_train_fold.assign(label=y_train_fold),
                sample_weights=weights_fold,
                **model_kwargs
            )
        else:
            raise ValueError("model_class must be callable")
        
        # Evaluate
        metrics = evaluate_model(
            model=model,
            X_test=X_test_fold,
            y_test=y_test_fold,
            feature_columns=feature_columns,
        )
        
        fold_metrics.append(metrics)
    
    return fold_metrics


def aggregate_cv_metrics(fold_metrics: List[EvalMetrics]) -> Dict[str, Any]:
    """Aggregate metrics across CV folds.
    
    Args:
        fold_metrics: List of EvalMetrics from each fold
        
    Returns:
        Dictionary with mean and std for each metric
    """
    metrics_dict = {
        "auroc_mean": np.mean([m.auroc for m in fold_metrics if not np.isnan(m.auroc)]),
        "auroc_std": np.std([m.auroc for m in fold_metrics if not np.isnan(m.auroc)]),
        "aucpr_mean": np.mean([m.aucpr for m in fold_metrics if not np.isnan(m.aucpr)]),
        "aucpr_std": np.std([m.aucpr for m in fold_metrics if not np.isnan(m.aucpr)]),
        "sensitivity_top5pct_mean": np.mean([m.sensitivity_top5pct for m in fold_metrics]),
        "sensitivity_top5pct_std": np.std([m.sensitivity_top5pct for m in fold_metrics]),
        "spatial_coverage_mean": np.mean([m.spatial_coverage for m in fold_metrics if not np.isnan(m.spatial_coverage)]),
        "spatial_coverage_std": np.std([m.spatial_coverage for m in fold_metrics if not np.isnan(m.spatial_coverage)]),
        "temporal_lead_time_mean": np.mean([m.temporal_lead_time for m in fold_metrics if not np.isnan(m.temporal_lead_time)]),
        "temporal_lead_time_std": np.std([m.temporal_lead_time for m in fold_metrics if not np.isnan(m.temporal_lead_time)]),
        "n_folds": len(fold_metrics),
    }
    
    return metrics_dict


def print_evaluation_report(metrics: EvalMetrics, model_name: str = "Model") -> None:
    """Print a formatted evaluation report.
    
    Args:
        metrics: EvalMetrics object
        model_name: Name of the model for display
    """
    print(f"\n{'='*60}")
    print(f"Evaluation Report: {model_name}")
    print(f"{'='*60}")
    print(f"AUROC:                    {metrics.auroc:.4f}")
    print(f"AUCPR:                    {metrics.aucpr:.4f}")
    print(f"Sensitivity @ top-5%:     {metrics.sensitivity_top5pct:.4f}")
    
    if not np.isnan(metrics.spatial_coverage):
        print(f"Spatial Coverage:         {metrics.spatial_coverage:.4f} ({metrics.spatial_coverage*100:.1f}%)")
    else:
        print(f"Spatial Coverage:         N/A (country codes not provided)")
    
    if not np.isnan(metrics.temporal_lead_time):
        print(f"Temporal Lead Time:       {metrics.temporal_lead_time:.2f} months")
    else:
        print(f"Temporal Lead Time:       N/A (dates not provided)")
    
    if metrics.precision_at_top5pct is not None:
        print(f"\nAdditional Metrics:")
        print(f"Precision @ top-5%:       {metrics.precision_at_top5pct:.4f}")
        print(f"Recall @ top-5%:          {metrics.recall_at_top5pct:.4f}")
    
    if metrics.n_positives is not None:
        print(f"\nDataset Statistics:")
        print(f"Positive samples:         {metrics.n_positives}")
        print(f"Negative samples:         {metrics.n_negatives}")
        print(f"Class balance:            {metrics.n_positives/(metrics.n_positives+metrics.n_negatives):.4f}")
    
    print(f"{'='*60}\n")
