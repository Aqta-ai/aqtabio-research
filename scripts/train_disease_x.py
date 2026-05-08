#!/usr/bin/env python3
"""
Train the dedicated Disease X classifier.

This is the v0.2.0 replacement for the probabilistic-union heuristic
currently behind the MCP `get_disease_x_risk` tool. Same XGBoost +
SHAP architecture as the per-pathogen models, different label:
positive = ANY zoonotic spillover within `lookback_months` from this
tile, regardless of which specific pathogen.

Prerequisites:
    - DATABASE_URL points to an Aurora instance with `features` and
      `tile_predictions` populated for the validation cohort tiles.
    - Historical features ingested for the lookback windows of every
      event in HISTORICAL_SPILLOVERS (this is the medRxiv preprint
      data-engineering blocker). Without this, the script will warn
      and use only whatever features are present.

Usage:
    export DATABASE_URL="postgresql://..."
    python scripts/train_disease_x.py \
        --output models/disease-x/model.ubj \
        --positive-events-file aqta_bio/backtesting/historical_events.py \
        --negative-sample-ratio 20 \
        --random-seed 42

Output:
    models/disease-x/model.ubj   — XGBoost booster
    models/disease-x/model_card.md — feature columns, training metrics, drift metadata

Once shipped, replace the probabilistic-union body of
`get_disease_x_risk` in aqta-mcp/server.py with a call into the
trained classifier (same pattern as the per-pathogen score lookup).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger("train_disease_x")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Default feature columns — MUST match the per-pathogen models so SHAP
# attributions are interpretable across the same feature space.
FEATURE_COLS = [
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--output", default="models/disease-x/model.ubj",
                   help="Where to write the trained XGBoost booster (.ubj)")
    p.add_argument("--negative-sample-ratio", type=int, default=20,
                   help="N negative tile-months per positive (default 20)")
    p.add_argument("--lookback-months", type=int, default=12,
                   help="Months before each spillover to label as positive (default 12)")
    p.add_argument("--test-fraction", type=float, default=0.20,
                   help="Held-out test set fraction (default 0.20)")
    p.add_argument("--random-seed", type=int, default=42)
    p.add_argument("--db-url", default=None,
                   help="DATABASE_URL override (defaults to env var)")
    return p.parse_args()


def make_engine(db_url: str | None):
    from sqlalchemy import create_engine
    url = db_url or os.environ.get("DATABASE_URL")
    if not url:
        logger.error("DATABASE_URL not set. Pass --db-url or export the env var.")
        sys.exit(2)
    return create_engine(url, pool_pre_ping=True)


def load_positive_tile_months(engine) -> list:
    """
    Build positive-class set: every (tile_id, month) pair within the
    lookback window of any historical spillover.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from aqta_bio.backtesting.historical_events import HISTORICAL_SPILLOVERS

    positives = []
    from sqlalchemy import text
    with engine.connect() as conn:
        for sp in HISTORICAL_SPILLOVERS:
            # Find nearest tile (lat/lon → tile_id) in features table
            row = conn.execute(text("""
                SELECT tile_id
                FROM tiles
                ORDER BY (centroid_lat - :lat) * (centroid_lat - :lat)
                       + (centroid_lon - :lon) * (centroid_lon - :lon)
                LIMIT 1
            """), {"lat": sp.location[0], "lon": sp.location[1]}).fetchone()
            if not row:
                logger.warning("No tile near %s @ %s", sp.event_id, sp.location)
                continue
            tile_id = row[0]
            # Generate the lookback window months
            d = sp.spillover_date
            for k in range(sp.lookback_months):
                m = (d - timedelta(days=30 * k)).strftime("%Y-%m")
                positives.append((tile_id, m, sp.event_id))
    logger.info("Built %d positive (tile, month) labels across %d historical events",
                len(positives), len(HISTORICAL_SPILLOVERS))
    return positives


def load_features_for_pairs(engine, pairs: list, label_value: int) -> "list[dict]":
    """For each (tile_id, month) load the features row, attach `label`."""
    from sqlalchemy import text
    rows = []
    with engine.connect() as conn:
        for tile_id, month, *rest in pairs:
            r = conn.execute(text(f"""
                SELECT {", ".join(FEATURE_COLS)}
                FROM features
                WHERE tile_id = :tile_id
                  AND TO_CHAR(period, 'YYYY-MM') = :month
                LIMIT 1
            """), {"tile_id": tile_id, "month": month}).fetchone()
            if r is None:
                continue
            row = dict(zip(FEATURE_COLS, r))
            row["label"] = label_value
            row["tile_id"] = tile_id
            row["month"] = month
            rows.append(row)
    return rows


def sample_negatives(engine, n: int, exclude_pairs: set, seed: int) -> list:
    """Random sample of (tile_id, month) pairs NOT in exclude set."""
    import random
    from sqlalchemy import text
    rng = random.Random(seed)
    with engine.connect() as conn:
        all_pairs = conn.execute(text("""
            SELECT tile_id, TO_CHAR(period, 'YYYY-MM')
            FROM features
        """)).fetchall()
    candidates = [(t, m) for (t, m) in all_pairs if (t, m) not in exclude_pairs]
    rng.shuffle(candidates)
    return candidates[:n]


def train(args: argparse.Namespace) -> None:
    try:
        import numpy as np
        import pandas as pd
        import xgboost as xgb
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
    except ImportError as exc:
        logger.error("Missing ML deps: %s — install with `pip install xgboost scikit-learn pandas numpy`", exc)
        sys.exit(2)

    engine = make_engine(args.db_url)

    pos_pairs = load_positive_tile_months(engine)
    pos_set = {(t, m) for (t, m, *_rest) in pos_pairs}

    logger.info("Loading positive features (this may take a few minutes)...")
    pos_rows = load_features_for_pairs(engine, pos_pairs, label_value=1)
    if not pos_rows:
        logger.error("No positive features loaded. Has the historical feature pipeline been ingested?")
        logger.error("This is the medRxiv preprint data-engineering blocker.")
        sys.exit(3)
    logger.info("Positive rows with features: %d", len(pos_rows))

    logger.info("Sampling negatives at %dx the positive count...", args.negative_sample_ratio)
    neg_pairs = sample_negatives(
        engine,
        n=len(pos_rows) * args.negative_sample_ratio,
        exclude_pairs=pos_set,
        seed=args.random_seed,
    )
    neg_rows = load_features_for_pairs(engine, neg_pairs, label_value=0)
    logger.info("Negative rows with features: %d", len(neg_rows))

    df = pd.DataFrame(pos_rows + neg_rows).dropna(subset=FEATURE_COLS)
    logger.info("Final training table: %d rows × %d features", len(df), len(FEATURE_COLS))

    X = df[FEATURE_COLS].astype(float)
    y = df["label"].astype(int)

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y,
        test_size=args.test_fraction,
        random_state=args.random_seed,
        stratify=y,
    )

    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        scale_pos_weight=args.negative_sample_ratio,  # rebalance against negative oversampling
        eval_metric="aucpr",
        random_state=args.random_seed,
    )
    logger.info("Fitting XGBoost...")
    model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=20)

    y_pred = model.predict_proba(X_te)[:, 1]
    metrics = {
        "auroc": float(roc_auc_score(y_te, y_pred)),
        "aucpr": float(average_precision_score(y_te, y_pred)),
        "brier": float(brier_score_loss(y_te, y_pred)),
        "n_train": int(len(X_tr)),
        "n_test": int(len(X_te)),
        "positive_rate_train": float(y_tr.mean()),
        "positive_rate_test": float(y_te.mean()),
    }
    logger.info("Held-out metrics: %s", json.dumps(metrics, indent=2))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    model.get_booster().save_model(str(out_path))
    logger.info("Wrote model to %s", out_path)

    # Model card alongside the .ubj
    card_path = out_path.parent / "model_card.md"
    card_path.write_text(f"""# Disease X model card (v0.2.0)

Pathogen-agnostic spillover-risk classifier. Positive = ANY zoonotic
spillover within {args.lookback_months} months from this tile.

## Training

- Positive (tile, month) pairs: {len(pos_rows)}
- Negative (sampled): {len(neg_rows)} ({args.negative_sample_ratio}× ratio)
- Train/test split: {1 - args.test_fraction:.0%}/{args.test_fraction:.0%}
- Random seed: {args.random_seed}

## Held-out metrics

| Metric | Value |
|---|---|
| AUROC | {metrics['auroc']:.4f} |
| AUCPR | {metrics['aucpr']:.4f} |
| Brier | {metrics['brier']:.4f} |

## Feature columns ({len(FEATURE_COLS)})

{chr(10).join(f"- `{c}`" for c in FEATURE_COLS)}

## Provenance

- Cohort: `aqta_bio/backtesting/historical_events.py` (25 events, 2003-2024)
- Negative sampling: random tile-months not in any spillover lookback window
- Training script: `scripts/train_disease_x.py`
- Reproducibility: deterministic given DATABASE_URL state and `--random-seed`
""")
    logger.info("Wrote model card to %s", card_path)


if __name__ == "__main__":
    train(parse_args())
