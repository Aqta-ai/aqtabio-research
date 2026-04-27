# Model Evaluation Module

## Overview

The evaluation module (`aqta_bio/model/evaluation.py`) implements the comprehensive evaluation metrics required by **Requirement 4.3** for the Aqta Bio spillover prediction platform.

## Metrics Implemented

### 1. AUROC (Area Under ROC Curve)
- Measures overall discrimination ability
- Range: [0, 1], higher is better
- Threshold-independent metric

### 2. AUCPR (Area Under Precision-Recall Curve)
- More informative for imbalanced datasets
- Range: [0, 1], higher is better
- Particularly important given 10:1 negative:positive ratio

### 3. Sensitivity at Top-5% Risk Tiles
- **Key operational metric**: "If we focus resources on the top 5% highest-risk tiles, what percentage of actual spillover events would we catch?"
- Directly measures early warning effectiveness
- Also computes precision and recall at top-5%

### 4. Spatial Coverage
- **Definition**: Percentage of countries (with at least 1 positive) that have at least 1 true positive in the top decile of predictions
- **Purpose**: Measures geographic generalization
- **Interpretation**: 
  - High coverage (>0.7): Model identifies risk across multiple countries
  - Low coverage (<0.5): Model concentrates predictions in few regions
- Configurable threshold: top decile (10%) or top 5%

### 5. Temporal Lead Time
- **Definition**: Average number of months in advance the model predicts spillover events that actually occur
- **Computation**: For true positives in top 10% of predictions, compute time difference between prediction date and event date
- **Interpretation**: Higher lead time = more advance warning for public health response

## Usage

### Basic Evaluation

```python
from aqta_bio.model.evaluation import evaluate_model

# Train your model
model, _ = train_xgboost(train_df, sample_weights)

# Evaluate on test set
metrics = evaluate_model(
    model=model,
    X_test=X_test,
    y_test=y_test,
    country_codes=test_countries,  # Optional: for spatial coverage
    event_dates=test_event_dates,  # Optional: for temporal lead time
    prediction_dates=test_pred_dates,  # Optional: for temporal lead time
)

# Print report
print_evaluation_report(metrics, model_name="M3 - XGBoost")
```

### Spatial Cross-Validation

```python
from aqta_bio.model.evaluation import evaluate_with_spatial_cv, aggregate_cv_metrics
from aqta_bio.dataset.cv import spatial_loocv_folds

# Generate spatial CV folds (leave-one-region-out)
folds = spatial_loocv_folds(X, regions)

# Evaluate with spatial CV
fold_metrics = evaluate_with_spatial_cv(
    model_class=train_xgboost,
    X=X,
    y=y,
    cv_folds=folds,
    sample_weights=sample_weights,
)

# Aggregate results
agg_metrics = aggregate_cv_metrics(fold_metrics)
print(f"AUROC: {agg_metrics['auroc_mean']:.4f} ± {agg_metrics['auroc_std']:.4f}")
```

### Individual Metric Computation

```python
from aqta_bio.model.evaluation import (
    compute_auroc,
    compute_aucpr,
    compute_sensitivity_at_top_k_percent,
    compute_spatial_coverage,
    compute_temporal_lead_time,
)

# Get predictions
y_pred_proba = model.predict_proba(X_test)[:, 1]

# Compute individual metrics
auroc = compute_auroc(y_test, y_pred_proba)
aucpr = compute_aucpr(y_test, y_pred_proba)

sensitivity, precision, recall = compute_sensitivity_at_top_k_percent(
    y_test, y_pred_proba, k_percent=5.0
)

spatial_cov = compute_spatial_coverage(
    y_test, y_pred_proba, country_codes, top_decile=True
)

lead_time = compute_temporal_lead_time(
    y_test, y_pred_proba, event_dates, prediction_dates
)
```

## Evaluation Script

The `scripts/evaluate_all_models.py` script evaluates all three models (M1, M2, M3) with the full metric suite:

```bash
# Evaluate all models
python scripts/evaluate_all_models.py \
    --labels-path data/processed/labeled_dataset.parquet \
    --output-path models/evaluation_results.json

# Skip spatial CV for faster evaluation
python scripts/evaluate_all_models.py --skip-spatial-cv
```

### Output

The script produces:
1. **Console output**: Formatted evaluation reports for each model
2. **JSON file**: Complete evaluation results saved to `models/evaluation_results.json`
3. **M4 gate decision**: Checks if M3 AUCPR > 0.65 to determine if M4 (GNN) should be trained

Example output:
```
============================================================
Evaluation Report: M3 - XGBoost
============================================================
AUROC:                    0.8847
AUCPR:                    0.7234
Sensitivity @ top-5%:     0.6500
Spatial Coverage:         0.7500 (75.0%)
Temporal Lead Time:       4.82 months

Additional Metrics:
Precision @ top-5%:       0.8200
Recall @ top-5%:          0.6500

Dataset Statistics:
Positive samples:         200
Negative samples:         2000
Class balance:            0.0909
============================================================
```

## EvalMetrics Dataclass

The `EvalMetrics` dataclass stores all evaluation results:

```python
@dataclass
class EvalMetrics:
    auroc: float
    aucpr: float
    sensitivity_top5pct: float
    spatial_coverage: float
    temporal_lead_time: float
    
    # Optional diagnostic metrics
    precision_at_top5pct: Optional[float] = None
    recall_at_top5pct: Optional[float] = None
    n_positives: Optional[int] = None
    n_negatives: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
```

## Requirement Validation

This module validates **Requirement 4.3**:

> WHEN evaluating models, THE Model_Registry SHALL compute AUROC, AUCPR, sensitivity at top-5% risk tiles, spatial coverage (percentage of countries with at least 1 true positive in the top decile), and temporal lead time.

All five metrics are implemented and tested with comprehensive unit tests in `tests/test_evaluation.py`.

## M4 (GNN) Training Gate

Per **Requirement 4.4**:

> WHEN M3 achieves AUCPR greater than 0.65, THE Model_Registry SHALL proceed to train M4 (Spatial GNN using GraphSAGE via torch-geometric).

The evaluation script automatically checks this threshold and reports whether M4 training should proceed.

If M3 AUCPR ≤ 0.65, a diagnostic report is generated per **Requirement 4.5**:

> IF M3 AUCPR remains below 0.65 after hyperparameter tuning, THE Model_Registry SHALL log a diagnostic report identifying likely causes (insufficient positive samples, feature quality issues, geographic sparsity) and SHALL NOT proceed to M4 training.

## Testing

Run the evaluation module tests:

```bash
pytest tests/test_evaluation.py -v
```

All 27 tests cover:
- AUROC computation (perfect, random, realistic predictions)
- AUCPR computation (perfect, realistic, single-class edge cases)
- Sensitivity at top-k% (different k values, bounds checking)
- Spatial coverage (perfect, partial, no positives)
- Temporal lead time (consistent, no TPs, datetime conversion)
- Full model evaluation (with/without spatial and temporal data)
- CV metrics aggregation
- Requirement 4.3 validation

## Performance Considerations

- **AUROC/AUCPR**: O(n log n) due to sorting
- **Sensitivity at top-k%**: O(n log n) due to sorting
- **Spatial coverage**: O(n × c) where c = number of countries (typically small)
- **Temporal lead time**: O(n) for date arithmetic
- **Spatial CV**: O(k × n) where k = number of folds (typically 2-4 for region-based CV)

For large datasets (>100K samples), consider:
1. Sampling for spatial CV evaluation
2. Caching predictions to avoid recomputation
3. Parallel fold evaluation

## Future Enhancements

Potential additions for v0.2+:
1. **Calibration metrics**: Brier score, calibration curves
2. **Fairness metrics**: Recall parity across income groups (already in governance module)
3. **Uncertainty quantification**: Prediction interval coverage
4. **Multi-pathogen evaluation**: Compare metrics across Ebola, H5N1, CCHFV, WNV
5. **Temporal stability**: Track metric drift over time
