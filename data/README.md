# `data/` — citable data artefacts

Static data files that document AqtaBio's recorded outputs in a form a
reviewer or downstream agent can `curl`, parse, and cite without running
the live MCP server.

## Files

### `recorded-attestations.json`

The seven anchor events surfaced by the live MCP tool
[`retrospective_validation`](../aqta-mcp/server.py). Each entry contains:

- `event_name` — display name
- `pathogen` / `pathogen_display` — pathogen ID and human-readable name
- `location` — text location and `tile_id` (the 25 km tile the model scored)
- `threshold_crossed_date` / `threshold_crossed_score` — the date the
  recorded attestation crossed the 0.72 alert threshold and the score at
  that point
- `official_notification` — the corresponding source-of-truth notification
  (WHO Disease Outbreak News, ECDC weekly bulletin, national MoH record)
- `pheic_declaration` — present where applicable (COVID-19, Mpox)
- `lead_time_days` — calculated lead time = `(notification_date − threshold_date)`
- `top_drivers` — the top SHAP feature names attributed for that event

### Important provenance note

These attestations are **frozen at the v0.1.0 development cycle**. They are
**not** a live model recompute against archival features — the historical
feature pipeline (ERA5 archive, Hansen yearly forest-loss, WorldPop yearly,
FAO GLW4, etc.) for these specific tiles has not yet been ingested into
the production atlas, which begins May 2024. The independently auditable
parts of these records are:

- The official notification dates (WHO / ECDC / MoH)
- The event metadata (location, pathogen, calendar dates)

The recorded model scores and threshold-crossing dates are **development-
cycle outputs**, useful as illustrative anchors against the historical
timeline. The live cross-pathogen recompute with AUROC, AUCPR, and
lead-time distribution is the deliverable of the forthcoming medRxiv
preprint, targeted Q3 2026. See [`docs/research/known-limitations.md`](../docs/research/known-limitations.md)
for the full provenance trail.

## Citation

```bibtex
@misc{aqtabio_attestations_v0_1_0,
  title  = {AqtaBio recorded retrospective attestations (v0.1.0)},
  author = {Chueayen, Anya},
  year   = {2026},
  url    = {https://github.com/Aqta-ai/aqtabio-research/blob/main/data/recorded-attestations.json},
  note   = {Frozen development-cycle attestations; live recompute pending Q3 2026 medRxiv preprint.}
}
```
