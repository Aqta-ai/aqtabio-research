# Known limitations (v0.1.0)

The honest framing for any reviewer, partner, or downstream user of AqtaBio v0.1.0. These limits are stated up front rather than buried.

## What the system can do today

- Score a 25 km tile against a pathogen-specific XGBoost model trained on open environmental, ecological, and socioeconomic data layers (ERA5, Hansen, WorldPop, FAO GLW4, IUCN, ACLED, MODIS, OpenStreetMap).
- Produce a SHAP attribution per prediction so that downstream agents and human reviewers can see which features drove the score.
- Emit FHIR R4 transaction Bundles round-trip-tested against the public HAPI FHIR test server.
- Return a consistent recorded retrospective attestation (threshold-crossing date, risk score, source-of-truth notification date, calculated lead time in days) for seven anchor events: 2019 Wuhan SARS-CoV-2, 2014 West Africa Ebola, 2018 DRC Ebola, 2018 WNV Italy, 2018 CCHFV Turkey, 2023 Marburg Equatorial Guinea, 2022 Mpox global outbreak.

## What the system cannot do today

### 1. The retrospective attestations are recorded, not live-recomputed

The seven anchor records returned by the MCP server's `retrospective_validation` tool are constants captured during the v0.1.0 development cycle. They are not produced by re-running the live model on archival features for the event tile. The historical feature pipeline for these tiles has not yet been ingested into the production atlas, which begins May 2024.

The numbers are useful as illustrative anchors against the documented historical timeline, but until the live recompute is published, they are *attestations* and not *verifications*. A cross-pathogen aggregate retrospective with AUROC, AUCPR, and lead-time distribution across the full 25-event historical cohort is the explicit deliverable of the forthcoming medRxiv preprint, target Q3 2026.

### 2. No prospective deployment

All evaluation in this release is retrospective against the held-out historical cohort. No public-health responder has yet acted on a real-time AqtaBio alert. The lead-time figures are counterfactuals against the historical record, not measured intervention outcomes.

### 3. Sparse operational coverage

The seeded production atlas is 578 tiles at 25 km resolution, against an 80,000+ tile roadmap. Coverage is densest in sub-Saharan Africa, eastern Europe, and Southeast Asia, with significant gaps in South Asia, the Andes, and the Arctic.

### 4. No external evaluator

No party outside Aqta Technologies Limited has independently re-run the validation. The medRxiv submission is the path to that. The validation cohort is defined in `aqta_bio/backtesting/historical_events.py` and is reproducible from open data; we welcome independent reanalysis.

### 5. No regulatory clearance

No conformity assessment has been completed under the EU AI Act (Regulation (EU) 2024/1689), EU MDR (Regulation (EU) 2017/745), or US FDA Software-as-a-Medical-Device pathways. The intended path is documented at [`docs/regulatory/ce-marking-and-eu-ai-act.md`](../regulatory/ce-marking-and-eu-ai-act.md). AqtaBio v0.1.0 is not approved for individual-patient clinical decision-making; outputs are population-level and intended only to inform pre-positioning decisions by public-health agencies.

### 6. Aggregate model-performance metrics are pending

Aggregate cross-pathogen AUROC, AUCPR, F1 at 0.72 alert threshold, Brier score, and false-positive rate are pending the medRxiv preprint validation cohort. Pathogen-specific backtests have produced AUROC values up to 0.975 for ebola alone (held-out time-aware splits), but a single aggregate value across all five operational pathogens has not been computed at the time of this release.

## How to interpret the public claims

| Claim type | Treat as |
|---|---|
| Source-of-truth notification dates (WHO DON, ECDC, MoH bulletins) | Independently auditable, citeable. |
| Recorded model attestation values for the seven anchor events (e.g., 0.82 score on Hubei, November 2019) | Frozen development-cycle output. Pending live recompute and peer review. |
| Aggregate AUROC, AUCPR, etc. | Pending. Reported in the forthcoming medRxiv preprint. |
| Lead-time figures (53, 67, 58, 87, 62, 72, 48 days) | Calculated from the recorded attestations against verifiable notification dates. Same provenance caveat applies. |
| Open data layers cited | Independently verifiable through the cited DOIs and source URLs. |

## Roadmap to closing each gap

| Gap | Target |
|---|---|
| Historical feature pipeline ingestion (ERA5 archive, Hansen yearly, WorldPop yearly) for the 25-event cohort | Q2–Q3 2026 |
| Live retrospective recompute against the cohort | Q3 2026 (input to the preprint) |
| medRxiv preprint with aggregate AUROC, AUCPR, lead-time distribution and bootstrap CIs | Q3 2026 |
| EU AI Act gap analysis (Articles 8–17) | Q3 2026 |
| ISO/IEC 42001:2023 management-system implementation | Q4 2026 onwards |
| First evaluation-pilot MOU with a public-health agency | Q4 2026 target |
| Tile-grid expansion to 80,000+ tiles | Q1 2027 target |

These are stated commitments. Progress will be reported in subsequent releases of this repository and through the medRxiv preprint.
