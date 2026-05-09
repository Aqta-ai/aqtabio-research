# Commitment file schema

```jsonc
{
  "iso_week": "2026-W19",            // ISO 8601 week identifier
  "generated_at": "2026-05-09T12:00:00Z",   // UTC timestamp of MCP query
  "evaluation_window": {
    "start": "2026-05-04",           // first day of the ISO week (inclusive)
    "end":   "2026-05-10"            // last day of the ISO week (inclusive)
  },
  "model": {
    "name":   "AqtaBio XGBoost ensemble",
    "version": "v0.1.0",
    "image_digest": "sha256:5f1e79d3...",   // App Runner image at gen time
    "mcp_endpoint": "https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp"
  },
  "method": {
    "tile_pool": "Lambda /tiles?pathogen={p}&limit=20",
    "selection": "highest risk_score, prefer non-saturated (p90 - p10 > 0.001)",
    "top_n_per_pathogen": 5
  },
  "pathogens_covered": [
    "ebola", "h5n1", "cchfv", "wnv", "sea-cov"
  ],
  "pathogens_pending_tile_seeding": [
    "mpox", "nipah", "hantavirus"
  ],
  "tiles": [
    {
      "pathogen": "ebola",
      "rank":      1,
      "tile_id":   "AF-025-10010",
      "country_iso3": "CAF",
      "region":    "Congo Basin",
      "month":     "2026-05",
      "risk_score":  0.999,
      "p10":         0.999,
      "p90":         1.000,
      "uncertainty_band": 0.001,
      "top_drivers": [
        "distance_to_past_spillover_log",
        "biotic_transition_index",
        "population_density_log"
      ]
    }
    // ... up to 5 tiles per pathogen × 5 pathogens = 25 entries
  ],
  "honest_caveats": [
    "Risk score is population-level for a 25 km tile, not a per-patient diagnostic.",
    "Coverage is sparse (578 production tiles); outbreaks in unseeded tiles record as `coverage_gap`, not `miss`.",
    "No claim that an outbreak WILL occur in the listed tiles; the commitment is that AqtaBio considered these tiles highest-risk for the named pathogen during the named window."
  ]
}
```

## Field definitions

- **`iso_week`**: ISO 8601 week (e.g. `2026-W19` = 4–10 May 2026).
- **`generated_at`**: UTC timestamp at which the MCP was queried.
- **`evaluation_window`**: closed-on-both-ends date range the
  commitment applies to. An outbreak is matched against the most
  recent commitment whose `evaluation_window.start` is on or before
  the outbreak's first symptom-onset date (or notification date if
  onset is unavailable).
- **`model.image_digest`**: the App Runner ECR image digest at the
  moment of generation. A subsequent model update does not
  invalidate prior commitments — they were made by the model that
  was live then.
- **`tiles[].rank`**: 1-indexed within the pathogen group; rank 1
  is the highest-risk tile for that pathogen.
- **`tiles[].uncertainty_band`**: `p90 - p10`, the 80% credible
  interval width.
- **`tiles[].top_drivers`**: the highest-magnitude SHAP features
  for that tile/month/pathogen, in descending order.

## Append-only invariant

Files in this folder are NEVER overwritten. A commitment for a
given ISO week is fixed at the moment of the commit. The
verification protocol uses the file as it appeared in the public
git history at the relevant date, not the current HEAD.

If a tile-id, pathogen-id, or scoring scheme changes in a future
v0.2.0+ release, that change is recorded in the `model.version`
field of the next commitment. Old commitments remain valid against
the model that produced them.
