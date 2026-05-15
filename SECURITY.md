# Security policy and distribution scope

## Reporting a security issue

If you find a vulnerability in the code published in this repository (the AqtaBio MCP server, the governance framework, the model wrapper code, or any of the supporting scripts), please **do not file a public GitHub issue.** Instead, email <security@aqta.ai> with:

- A description of the issue
- Steps to reproduce
- The version / commit you tested against
- Your name and contact information so we can credit your disclosure if you wish

We aim to acknowledge reports within 5 working days and to provide a timeline for remediation within 14 days. We do not currently run a paid bug-bounty programme; responsible disclosures will be acknowledged in release notes.

If the issue concerns the live MCP endpoint or the production REST API, please flag clearly so we can prioritise. Endpoint addresses are shared with partners under engagement at <partnerships@aqtabio.org>.

## What's in scope of this repository

The code in this repository is the **public research mirror** for AqtaBio. It is licensed under Apache 2.0. You may inspect it, fork it, cite it, and reuse it under the terms of the licence. Specifically the following are open:

- `aqta-mcp/` — Model Context Protocol server source code
- `aqta_bio/backtesting/historical_events.py` — the 25-event historical spillover cohort
- `aqta_bio/governance/` — the 8-layer bio-domain governance framework
- `aqta_bio/model/` — XGBoost + SHAP framework wrapper code (per-pathogen model cards in markdown form, not the trained weights)
- `scripts/train_disease_x.py` — training script for the dedicated Disease X classifier
- `data/recorded-attestations.json` — citable retrospective attestations
- `docs/research/` — methodology, validation framework, preprint outline, known limitations
- `docs/regulatory/` — EU AI Act Annex III §5(a) classification and 12-month conformity roadmap

## What's NOT in scope of this repository

The following components of the AqtaBio platform are **not** distributed here and are not part of the open release:

| Component | Why it's closed | Path to access |
|---|---|---|
| **Trained model artefacts** (`models/{pathogen}/model.ubj` per-pathogen XGBoost boosters) | Distributed under separate research-pilot agreement; not redistributable under Apache 2.0 | Email <partnerships@aqtabio.org> describing your research or pilot use case |
| **FastAPI backend** (`aqta_bio/api/`) | Production API server, auth flows, admin tooling | Closed source |
| **Data ingestion pipelines** (`aqta_bio/ingest/` for ERA5, Hansen, WorldPop, FAO GLW4, IUCN, ACLED, MODIS, OSM) | Proprietary feature engineering; ingestion harnesses developed by Aqta Technologies Limited | Closed source |
| **Production database** (Aurora PostgreSQL containing predictions, features, audit logs) | Operational state; access via the public REST API only | Public REST API at the Lambda URL above |
| **Frontend dashboard** (Next.js application at <https://aqtabio.org>) | Brand assets, customer-facing UX, role-based access controls | Closed source |
| **Infrastructure as code** (Terraform, deployment scripts, AWS configuration) | Operational security boundary | Closed source |
| **Internal pitch material**, grant applications, business strategy documents | Commercial-confidential | Closed source |

## If you want to use AqtaBio in research or piloting

- **For research using only the methodology / validation cohort / governance framework**: clone this repo, cite as below, no partnership needed.
- **For research that needs the trained models** (to reproduce per-pathogen risk scores or run new validation against held-out events): contact <partnerships@aqtabio.org> describing your research question, institution, and intended use. Trained models are released under a separate research-pilot agreement that includes citation, non-redistribution, and reasonable disclosure terms.
- **For evaluation pilots with public-health agencies** (Africa CDC, ECDC, national PHOs, WHO GOARN): contact <partnerships@aqtabio.org>. We're actively seeking first-pilot partners on the validation-cohort regions.
- **For commercial integration** (FHIR-based EMR vendors, biosurveillance platforms, healthcare AI orchestrators): contact <partnerships@aqtabio.org>.

## Citation

```bibtex
@misc{aqtabio_research_v0_1_0,
  title  = {AqtaBio — pre-etiologic zoonotic spillover risk forecasting (research mirror)},
  author = {Chueayen, Anya},
  year   = {2026},
  url    = {https://github.com/Aqta-ai/aqtabio-research},
  note   = {Apache 2.0 licensed. Trained models under separate research-pilot agreement.}
}
```

## Contact

- **Security disclosures**: <security@aqta.ai>
- **Research and partnership inquiries**: <partnerships@aqtabio.org>
- **General**: <hello@aqta.ai>
- **Pilot endpoint access**: <partnerships@aqtabio.org>
