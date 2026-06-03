# AqtaBio - Research artefacts

Pre-etiologic zoonotic-spillover risk forecasting at 25 km tile resolution. Includes the **first deployed pathogen-agnostic Disease X tool** addressing the WHO R&D Blueprint's eleventh priority - pre-emergence detection for the unknown pathogen of the next pandemic.

This repository is the **public research mirror** for the AqtaBio platform built by [Aqta Technologies Limited](https://aqta.ai) (Dublin, Ireland). It contains the live MCP server source, the 25-event validation cohort, the 8-layer bio-domain governance framework, the XGBoost + SHAP wrapper code and per-pathogen model cards, dated pre-event commitment files, and citable retrospective attestations. The closed product source - operational infrastructure, deployment configuration, customer-facing dashboard, internal pitch material - is not in this repository and is not part of the open release.

## Status

**v0.1.0 - research preview.** Not approved for clinical decision-making. Not approved for individual-patient diagnostic use. Outputs are population-level risk scores intended to inform pre-positioning decisions by public-health agencies. No conformity assessment under EU AI Act (Regulation (EU) 2024/1689), EU MDR, or US FDA has yet been completed; the regulatory positioning and classification rationale are maintained outside this repository and are available on request to <partnerships@aqtabio.org>.

**Aggregate validation pending.** The retrospective attestations for the seven anchor events distributed with this release were recorded during the v0.1.0 development cycle, not produced by a live recompute against the production atlas-tile pipeline (which begins May 2024). Pathogen-specific backtests have produced AUROC values up to 0.975 for ebola (held-out time-aware splits); a cross-pathogen aggregate AUROC, AUCPR, and lead-time distribution across the full 25-event cohort is the deliverable of the forthcoming medRxiv preprint, target Q3 2026. A focused capabilities-and-limits statement and the validation methodology are available on request.

## What is here

| Path | Purpose |
|---|---|
| [`aqta-mcp/`](aqta-mcp/) | Public MCP (Model Context Protocol) server source. **Nineteen tools** including `optimise_sentinel_placement` (active-learning surveillance recommender), `get_disease_x_risk` (pathogen-agnostic), FHIR R4 native, A2A v1.0 agent card, SNOMED CT pathogen codes. Live at `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp`. Usage examples in [`aqta-mcp/MCP_USAGE.md`](aqta-mcp/MCP_USAGE.md). |
| [`aqta_bio/backtesting/historical_events.py`](aqta_bio/backtesting/historical_events.py) | The 25-event historical spillover cohort (2003–2024), each anchored to a publicly verifiable WHO Disease Outbreak News, ECDC weekly bulletin, or national MoH notification date. |
| [`aqta_bio/governance/`](aqta_bio/governance/) | The 8-layer bio-domain governance gateway: data provenance, SHAP feature hash, model version pinning, 90-day data-freshness circuit breaker, HITL epidemiologist sign-off queue, RBAC, immutable audit log, bias monitoring. Specific to biosurveillance; separate codebase from the commercial Aqta runtime governance engine that lives in a different repository. |
| [`aqta_bio/model/`](aqta_bio/model/) | XGBoost + SHAP framework code and per-pathogen model cards. |

## What is **not** here

This is the research mirror; it is not a runnable copy of the production system. The closed source includes the FastAPI backend (`aqta_bio/api/`), the Next.js dashboard (`aqta-bio-dashboard/`), the data ingestion pipelines (`aqta_bio/ingest/`), AWS infrastructure and Terraform configuration, deployment scripts, internal pitch material, and proprietary brand assets. Some files included here import from those private modules (for example, `aqta_bio.config.get_database_url`); those imports will not resolve in isolation and are present only for inspection.

To exercise the live system, use the public MCP endpoint listed below. Curl examples in [`aqta-mcp/MCP_USAGE.md`](aqta-mcp/MCP_USAGE.md). A reference Python agent (Google ADK + Gemini) and a no-key smoke test live alongside the server source.

## Live endpoints

All endpoints are public and require no authentication. The canonical web entry point is <https://aqtabio.org/mcp> (connection snippets, sample prompts, and link-out to the live MCP); the AWS App Runner URL below is the programmatic target an MCP client connects to.

- **MCP server (programmatic)**: `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp` - nineteen tools including `optimise_sentinel_placement`, `retrospective_validation`, `get_risk_score`, `get_hotspots`, `generate_outbreak_briefing`, `submit_to_hapi_fhir`, `self_test`. Streamable HTTP transport (set `Accept: application/json, text/event-stream`). See [`aqta-mcp/MCP_USAGE.md`](aqta-mcp/MCP_USAGE.md).
- **A2A v1.0 agent card**: `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/.well-known/agent.json` - RFC 8615 well-known URI declaring capabilities and per-pathogen SNOMED CT codes.

## Validation cohort

Twenty-five historical zoonotic spillover events spanning 2003 to 2024 across Ebola, H5N1, Crimean-Congo Haemorrhagic Fever, West Nile virus, SARS-CoV-2, Mpox, Marburg, Lassa, Nipah, MERS-CoV, and Rift Valley Fever. Each event is anchored to:

- A 25 km tile by latitude/longitude
- A publicly verifiable source-of-truth notification date (WHO DON, ECDC, national MoH, peer-reviewed retrospective literature)
- A 12-month lookback window for evaluating the model's pre-spillover risk trajectory

The full cohort definition with citations lives in [`aqta_bio/backtesting/historical_events.py`](aqta_bio/backtesting/historical_events.py).

## Citation

If you reference AqtaBio in academic, technical, or product work prior to the medRxiv preprint, please cite this repository and the live MCP endpoint:

> Chueayen, A. (2026). *AqtaBio: pre-etiologic zoonotic spillover risk forecasting (v0.1.0).* Aqta Technologies Limited. https://github.com/Aqta-ai/aqtabio-research. Live MCP: https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp.

For the dated record of when each component of the MCP server entered the public mirror, see [`CHANGELOG.md`](CHANGELOG.md). The canonical timestamp for any specific tool or formulation is the corresponding git commit on `main` of this repository.

A formal preprint with the aggregate retrospective evaluation is in preparation. Target submission: Q3 2026 (medRxiv).

## Licence

Apache License 2.0. See [`LICENSE`](LICENSE) for the full text. The licence applies to the source code in this repository. The trained model artefacts (`models/{pathogen}/model.ubj`) are not distributed here; access is granted under separate research-pilot agreements; contact <hello@aqta.ai>.

## Honest gaps

- No prospective deployment (all evaluation is retrospective against the held-out historical cohort).
- No public-health responder has yet acted on a real-time AqtaBio alert. The lead-time claim is a counterfactual against the historical record.
- Geographic coverage is sparse at the operational tier (578 tiles seeded against an 80,000+ tile roadmap). Coverage is densest in sub-Saharan Africa, eastern Europe, and Southeast Asia.
- No external evaluator has independently re-run the validation. Aggregate live recompute is the explicit Q3 2026 deliverable.
- No regulatory clearance under EU AI Act, EU MDR, or US FDA. The regulatory positioning is maintained outside this repository and shared with pilot partners under engagement.

These are stated up front rather than buried. A focused statement of capabilities and limits is available on request to <partnerships@aqtabio.org>.

## Contact

Aqta Technologies Limited (Dublin, Ireland). Founder: Anya Chueayen. Public correspondence: <hello@aqta.ai>. Pilot enquiries (public-health agencies, ministries of health, GOARN coordinators): <partnerships@aqtabio.org>.
