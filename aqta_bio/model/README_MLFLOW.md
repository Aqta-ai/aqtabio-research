# MLflow Model Registry

This module implements the MLflow model registry for tracking and versioning trained models, as specified in Task 5.6 and Requirements 4.4, 4.5.

## Overview

The MLflow registry provides:

1. **Model Artifact Storage** with SHA-256 hash verification
2. **Version Tracking** with timestamps and unique model IDs
3. **Hyperparameter Logging** for reproducibility
4. **Metrics Tracking** (AUROC, AUCPR, sensitivity, spatial coverage, temporal lead time)
5. **M4 (GNN) Gating Logic** based on M3 AUCPR performance
6. **Diagnostic Reporting** when M3 AUCPR < 0.65

## Usage

### Registering a Model

```python
from aqta_bio.model import train_xgboost, evaluate_model
from aqta_bio.model.registry import register_model_in_mlflow

# Train model
model, report = train_xgboost(train_df, sample_weights)

# Evaluate model
metrics = evaluate_model(model, X_test, y_test)

# Register in MLflow
model_card = register_model_in_mlflow(
    model=model,
    model_type="xgboost",
    hyperparameters={
        "n_estimators": 1000,
        "learning_rate": 0.05,
        "max_depth": 7,
        "scale_pos_weight": 10.0,
    },
    metrics=metrics,
    experiment_name="aqta-bio-ebola-v01",
    pathogen_id="ebola",
)

print(f"Model registered: {model_card.model_id}")
print(f"SHA-256: {model_card.sha_hash}")
print(f"MLflow Run ID: {model_card.mlflow_run_id}")
```

### Registering with Quantile Models

For XGBoost models with confidence bands:

```python
from aqta_bio.model import train_quantile_regressors

# Train quantile regressors
quantile_models = train_quantile_regressors(
    train_df=train_df,
    sample_weights=sample_weights,
    quantiles=[0.1, 0.9],
)

# Register with quantile models
model_card = register_model_in_mlflow(
    model=model,
    model_type="xgboost",
    hyperparameters=hyperparameters,
    metrics=metrics,
    experiment_name="aqta-bio-ebola-v01",
    pathogen_id="ebola",
    quantile_models=quantile_models,  # Include confidence band models
)
```

### M4 (GNN) Gating Decision

The system automatically gates M4 (GNN) training based on M3 AUCPR:

```python
from aqta_bio.model.registry import should_train_gnn, log_diagnostic_report

# Check if M4 should be trained
if should_train_gnn(m3_metrics):
    print("✓ M3 AUCPR > 0.65 - M4 (GNN) training approved")
    # Proceed with M4 training (future task)
else:
    print("✗ M3 AUCPR < 0.65 - M4 (GNN) training skipped")
    # Log diagnostic report
    log_diagnostic_report(
        m3_metrics=m3_metrics,
        experiment_name="aqta-bio-ebola-v01",
        pathogen_id="ebola",
    )
```

### Loading a Model from MLflow

```python
from aqta_bio.model.registry import load_model_from_mlflow, verify_model_sha

# Load model by run ID
model = load_model_from_mlflow(run_id="abc123...")

# Verify SHA-256 hash
expected_sha = "..."  # From model card
if verify_model_sha(model, expected_sha):
    print("✓ Model SHA verified")
else:
    print("✗ Model SHA mismatch - artifact may be corrupted")
```

## Command-Line Script

Use the `scripts/register_models.py` script to register all trained models:

```bash
# Register models with default settings
python scripts/register_models.py

# Specify MLflow tracking URI
python scripts/register_models.py --mlflow-uri http://localhost:5000

# Specify pathogen and experiment
python scripts/register_models.py --pathogen ebola --experiment aqta-bio-ebola-v01

# Specify custom dataset path
python scripts/register_models.py --data-path data/processed/custom_dataset.parquet
```

The script will:
1. Load the dataset
2. Train M1 (Logistic Regression), M2 (Random Forest), M3 (XGBoost)
3. Evaluate each model
4. Register all models in MLflow
5. Check M3 AUCPR and gate M4 (GNN) training
6. Log diagnostic report if M3 AUCPR < 0.65

## Model Card Structure

Each registered model has a `ModelCard` with:

```python
@dataclass
class ModelCard:
    model_id: str                    # e.g., "ebola_xgboost_20240115_103000"
    model_type: str                  # "logistic", "rf", "xgboost", "gnn"
    version: str                     # e.g., "20240115.103000"
    sha_hash: str                    # SHA-256 hash of pickled model
    hyperparameters: Dict[str, Any]  # Training hyperparameters
    metrics: EvalMetrics             # Evaluation metrics
    training_timestamp: datetime     # UTC timestamp
    mlflow_run_id: str               # MLflow run ID
    pathogen_id: str                 # "ebola", "h5n1", etc.
```

## MLflow Experiment Structure

Models are organized by experiment:

- **aqta-bio-ebola-v01**: Ebola models (M1, M2, M3)
- **aqta-bio-h5n1-v02**: H5N1 models (future)
- **aqta-bio-cchfv-v03**: CCHFV models (future)
- **aqta-bio-wnv-v04**: WNV models (future)

Each run logs:
- **Parameters**: model_type, pathogen_id, hyperparameters, version, sha_hash
- **Metrics**: auroc, aucpr, sensitivity_top5pct, spatial_coverage, temporal_lead_time
- **Artifacts**: model artifact, quantile models (if applicable), model_card.json

## Diagnostic Report

When M3 AUCPR < 0.65, a diagnostic report is logged identifying likely causes:

1. **Insufficient Positive Samples**: Too few training examples
2. **Feature Quality Issues**: Poor discriminative power
3. **Geographic Sparsity**: Uneven spatial coverage
4. **Class Imbalance**: Extreme positive/negative ratio

The report includes:
- Current metrics (AUROC, AUCPR, spatial coverage)
- Sample counts (positives, negatives)
- Recommendations for improvement
- Next steps for debugging

## Viewing Results

Start the MLflow UI to view registered models:

```bash
mlflow ui --backend-store-uri ./mlruns
```

Then open http://localhost:5000 in your browser.

## Requirements Validation

This module validates:

- **Requirement 4.4**: Gate M4 (GNN) on M3 AUCPR > 0.65
- **Requirement 4.5**: Log diagnostic report if M3 AUCPR < 0.65 after tuning
- **Requirement 4.6**: Store model artifacts with SHA hash, version, timestamp, hyperparameters, metrics
- **Requirement 6.2**: Verify model artifact SHA matches MLflow registry on load

## Testing

Run the test suite:

```bash
pytest tests/test_model_registry.py -v
```

Tests cover:
- SHA-256 hash computation
- Model card serialization
- MLflow registration
- M4 gating logic
- Diagnostic report logging
- Model verification
- Experiment creation
