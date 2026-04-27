# AqtaBio — Research artefacts

Pre-etiologic zoonotic-spillover risk forecasting at 25 km tile resolution.

This repository is the **public research mirror** for the AqtaBio platform built by [Aqta Technologies Limited](https://aqta.ai) (Dublin, Ireland). It contains the methodology, validation cohort, governance framework, regulatory pathway note, MCP server source, and forthcoming-preprint scaffolding. The closed product source — operational infrastructure, deployment configuration, customer-facing dashboard, internal pitch material — is not in this repository and is not part of the open release.

## Status

**v0.1.0 — research preview.** Not approved for clinical decision-making. Not approved for individual-patient diagnostic use. Outputs are population-level risk scores intended to inform pre-positioning decisions by public-health agencies. No conformity assessment under EU AI Act, EU MDR, or US FDA has yet been completed; the regulatory pathway is documented in [`docs/regulatory/`](docs/regulatory/ce-marking-and-eu-ai-act.md).

**Aggregate validation pending.** The retrospective attestations for the seven anchor events distributed with this release were recorded during the v0.1.0 development cycle, not produced by a live recompute against the production atlas-tile pipeline (which begins May 2024). Pathogen-specific backtests have produced AUROC values up to 0.975 for ebola (held-out time-aware splits, see `reports/ebola/backtest_validation.json` in the closed source); a cross-pathogen aggregate AUROC, AUCPR, and lead-time distribution across the full 25-event cohort is the deliverable of the forthcoming medRxiv preprint, target Q3 2026. A focused statement of what the system can and cannot do today is at [`docs/research/known-limitations.md`](docs/research/known-limitations.md).

**Regulatory positioning.** AqtaBio is classified as a candidate high-risk AI system under EU AI Act (Regulation (EU) 2024/1689) Annex III §5(a) — public authorities using AI to evaluate eligibility for essential public services. The full classification rationale and a 12-month conformity roadmap aligned to ISO/IEC 42001:2023 (AI management system) is at [`docs/regulatory/ce-marking-and-eu-ai-act.md`](docs/regulatory/ce-marking-and-eu-ai-act.md).

## What is here

| Path | Purpose |
|---|---|
| [`aqta-mcp/`](aqta-mcp/) | Public MCP (Model Context Protocol) server source. Eleven tools, FHIR R4 native, A2A v1.0 agent card, SNOMED CT pathogen codes. Live at `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp`. |
| [`aqta_bio/backtesting/historical_events.py`](aqta_bio/backtesting/historical_events.py) | The 25-event historical spillover cohort (2003–2024), each anchored to a publicly verifiable WHO Disease Outbreak News, ECDC weekly bulletin, or national MoH notification date. |
| [`aqta_bio/governance/`](aqta_bio/governance/) | The 8-layer AqtaCore governance framework: data provenance, SHAP feature hash, model version pinning, staleness circuit breaker, HITL sign-off queue, RBAC, immutable audit log, bias monitoring. |
| [`aqta_bio/model/`](aqta_bio/model/) | XGBoost + SHAP framework code and per-pathogen model cards. |
| [`docs/research/`](docs/research/) | Methodology, validation framework, preprint outline, credibility audit, researcher API guide. |
| [`docs/regulatory/`](docs/regulatory/ce-marking-and-eu-ai-act.md) | EU AI Act (Regulation (EU) 2024/1689) Annex III §5(a) classification + 12-month conformity roadmap aligned to ISO/IEC 42001:2023. |

## What is **not** here

This is the research mirror; it is not a runnable copy of the production system. The closed source includes the FastAPI backend (`aqta_bio/api/`), the Next.js dashboard (`aqta-bio-dashboard/`), the data ingestion pipelines (`aqta_bio/ingest/`), AWS infrastructure and Terraform configuration, deployment scripts, internal pitch material, and proprietary brand assets. Some files included here import from those private modules (for example, `aqta_bio.config.get_database_url`); those imports will not resolve in isolation and are present only for inspection.

To exercise the live system, use the public MCP endpoint listed above or the public REST endpoints documented in [`docs/research/RESEARCHER_GUIDE.md`](docs/research/RESEARCHER_GUIDE.md).

## Live endpoints

All endpoints are public and require no authentication. The canonical web entry point is <https://aqtabio.org/mcp> (connection snippets, sample prompts, and link-out to the live MCP); the AWS App Runner URL below is the programmatic target an MCP client connects to.

- **MCP server (programmatic)**: `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp` — eleven tools including `retrospective_validation`, `get_risk_score`, `get_hotspots`, `generate_outbreak_briefing`, `emit_fhir_bundle`. Documentation at <https://aqtabio.org/mcp>.
- **A2A v1.0 agent card**: `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/.well-known/agent.json` — RFC 8615 well-known URI declaring capabilities and per-pathogen SNOMED CT codes.
- **Public REST API**: `https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws` — `/tiles`, `/pathogens/{p}/hotspot-count`, etc. See [`docs/research/RESEARCHER_GUIDE.md`](docs/research/RESEARCHER_GUIDE.md).

## Validation cohort

Twenty-five historical zoonotic spillover events spanning 2003 to 2024 across Ebola, H5N1, Crimean-Congo Haemorrhagic Fever, West Nile virus, SARS-CoV-2, Mpox, Marburg, Lassa, Nipah, MERS-CoV, and Rift Valley Fever. Each event is anchored to:

- A 25 km tile by latitude/longitude
- A publicly verifiable source-of-truth notification date (WHO DON, ECDC, national MoH, peer-reviewed retrospective literature)
- A 12-month lookback window for evaluating the model's pre-spillover risk trajectory

The full cohort definition with citations lives in [`aqta_bio/backtesting/historical_events.py`](aqta_bio/backtesting/historical_events.py).

## Citation

If you reference AqtaBio in academic work prior to the medRxiv preprint, please cite this repository and the live MCP endpoint:

> Chueayen, A. (2026). *AqtaBio: pre-etiologic zoonotic spillover risk forecasting (v0.1.0).* Aqta Technologies Limited. https://github.com/Aqta-ai/aqtabio-research. Live MCP: https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp.

A formal preprint with the aggregate retrospective evaluation is in preparation; outline at [`docs/research/preprint-outline.md`](docs/research/preprint-outline.md). Target submission: Q3 2026.

## Licence

Apache License 2.0. See [`LICENSE`](LICENSE) for the full text. The licence applies to the source code in this repository. The trained model artefacts (`models/{pathogen}/model.ubj`) are not distributed here; access is granted under separate research-pilot agreements; contact <hello@aqta.ai>.

## Honest gaps

- No prospective deployment (all evaluation is retrospective against the held-out historical cohort).
- No public-health responder has yet acted on a real-time AqtaBio alert. The lead-time claim is a counterfactual against the historical record.
- Geographic coverage is sparse at the operational tier (578 tiles seeded against an 80,000+ tile roadmap). Coverage is densest in sub-Saharan Africa, eastern Europe, and Southeast Asia.
- No external evaluator has independently re-run the validation. Aggregate live recompute is the explicit Q3 2026 deliverable.
- No regulatory clearance under EU AI Act, EU MDR, or US FDA. Path documented; first step is the gap analysis described in [`docs/regulatory/ce-marking-and-eu-ai-act.md`](docs/regulatory/ce-marking-and-eu-ai-act.md).

These are stated up front rather than buried. A focused statement of capabilities and limits is at [`docs/research/known-limitations.md`](docs/research/known-limitations.md).

## Contact

Aqta Technologies Limited (Dublin, Ireland). Founder: Anya Chueayen. Public correspondence: <hello@aqta.ai>. Pilot enquiries (public-health agencies, ministries of health, GOARN coordinators): <partnerships@aqtabio.org>.
