# AqtaBio Pandemic Risk — Prompt Opinion Agent Config

Use these values when creating the BYO Agent on app.promptopinion.ai.

---

## Agent Identity

- **Name**: AqtaBio Pandemic Risk Agent
- **Description**: Pre-etiologic zoonotic disease spillover early warning system. Predicts pandemic risk 53 days before WHO notification using XGBoost + SHAP + Claude AI. Operational for 5 priority pathogens across Africa (v0.1.0 pilot). Returns FHIR R4 resources.
- **Icon**: Use AqtaBio logo or a biohazard/globe icon
- **Category**: Healthcare / Public Health / Epidemiology

---

## MCP Server Connection

- **Transport**: Streamable HTTP
- **URL**: `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp`
- **Tools exposed**: 11
- **Extension**: `ai.promptopinion/fhir-context` declared in capabilities

---

## Tools

| # | Tool | Description |
|---|------|-------------|
| 1 | `list_pathogens` | List monitored pathogens with SNOMED codes and geographic scope |
| 2 | `get_risk_score` | Current spillover risk score for a tile, with SHAP drivers. FHIR RiskAssessment optional. |
| 3 | `get_hotspots` | Hotspot count by severity for a pathogen. FHIR DetectedIssue optional. |
| 4 | `get_risk_trend` | 24-month risk trajectory for a tile. FHIR Observation Bundle optional. |
| 5 | `get_top_risk_tiles` | Highest-risk tiles ranked by score |
| 6 | `get_system_status` | System health, data freshness, live vs demo mode |
| 7 | `generate_outbreak_briefing` | **[GenAI]** Claude synthesises hotspot + tile data into a PHO situational brief |
| 8 | `explain_risk_drivers` | **[GenAI]** Claude translates SHAP values into plain-English causal narrative + actions |
| 9 | `retrospective_validation` | **[VALIDATION]** Historical risk score + real WHO notification date for 6 outbreak events — makes the "53 days before WHO" claim live-testable |
| 10 | `get_multi_pathogen_hotspots` | **[SYNDEMIC]** Detects "threat multiplier" regimes where multiple pathogens hit HIGH+ severity simultaneously, flagging resource saturation |
| 11 | `generate_fhir_bundle_for_pho` | **[INTEGRATION]** Complete FHIR R4 transaction Bundle (RiskAssessment + DetectedIssue + 12 Observations) ready to POST to any EMR with zero transformation |

---

## Suggested System Prompt

```
You are the AqtaBio Pandemic Risk Agent, a public health surveillance assistant.
You help clinicians, epidemiologists, and public health officers assess zoonotic
disease spillover risk using pre-etiologic ML predictions — 53 days ahead of WHO
notification on average.

This is a v0.1.0 pilot covering 5 operational pathogens across Africa:
Ebola, H5N1, CCHF, West Nile, and SARS-CoV-2. Mpox (Monkeypox) is in pilot,
validated retrospectively on the 2022 global outbreak (48 days before the
Brussels index cluster, 125 days before the WHO PHEIC declaration).
Risk scores range from 0 (minimal) to 1 (critical).

When asked about risk, always:
1. Report the risk score and confidence interval (p10–p90)
2. Explain the top SHAP drivers in plain English
3. Give specific recommended actions based on the risk tier

For structured clinical integration, request fhir_format=true on any tool.
Use generate_outbreak_briefing for a full narrative situational report.
Use explain_risk_drivers to understand WHY a specific location is flagged.
```

---

## Sample Prompts

1. "What pathogens does AqtaBio monitor and where?"
2. "Generate a full situational brief for Ebola across Africa right now"
3. "Show me the current H5N1 hotspot count, use FHIR format"
4. "What are the top 10 highest-risk tiles for SARS-CoV-2 this month?"
5. "Explain why tile AT_sahel_12_5 has elevated Ebola risk, what should I do?"
6. "Get the 12-month risk trend for tile AF-025-3A7F for West Nile virus"
7. "Is the AqtaBio system healthy and using live data?"
8. "Validate AqtaBio's Mpox prediction on the 2022 global outbreak"
9. "Validate AqtaBio's COVID-19 prediction — what did we say about Wuhan in November 2019?"
10. "Is there a threat multiplier right now across all 5 operational pathogens?"
11. "Build a FHIR Bundle for tile AF-025-12345 Ebola so I can POST it to HAPI FHIR"

---

## FHIR / SHARP Context

All tools support `fhir_format=true` to return HL7 FHIR R4 resources:

| Resource | Tool | Use case |
|----------|------|----------|
| `RiskAssessment` | `get_risk_score` | Per-tile spillover probability |
| `DetectedIssue` | `get_hotspots` | Active outbreak alert with severity |
| `Observation` Bundle | `get_risk_trend` | Time-series risk trajectory |

- SNOMED CT codes for all 6 pathogens
- Tile identifiers: system `https://aqtabio.org/tiles`
- Model method: `https://aqtabio.org/models/xgboost-shap-v0.1.0`
- Server declares `ai.promptopinion/fhir-context` extension in capabilities

---

## The GenAI Difference (Judging Criterion 1)

Tools 1–6 expose ML data. Tools 7–8 are where Generative AI addresses a challenge
traditional rule-based software cannot:

**Problem:** A PHO receiving a risk score of 0.82 doesn't know what to do.
Traditional software outputs numbers. Only GenAI can translate:

> `deforestation_rate: 0.23, livestock_density: 0.18, temperature_anomaly: 0.15`

...into:

> *"Elevated risk in this region is driven by three converging factors: recent large-scale
> deforestation within 15 km of populated areas has expanded the bat-human interface;
> high livestock density at nearby markets creates additional spillover pathways; and
> an above-average temperature anomaly is extending the active season for intermediate
> hosts. Recommended actions: (1) Alert GOARN West Africa regional coordinator, (2)
> Initiate enhanced passive surveillance at the Bouaké livestock market, (3) Pre-position
> 200 rapid diagnostic kits to the nearest biosurveillance unit."*

**That is the Last Mile** — and it requires Claude.

---

## Demo Video Script (3 minutes)

**0:00–0:30 — Hook**
> "Every pandemic starts as a number no one acts on. AqtaBio puts the world's first
> pandemic intelligence agent directly into a clinician's AI workspace."

Show: Prompt Opinion workspace opening.

**0:30–1:00 — Discovery**
Call `get_hotspots(pathogen="h5n1")` live.
> "Seven tiles in Southeast Asia just crossed the critical threshold."
Show: FHIR DetectedIssue resource returned.

**1:00–1:45 — Intelligence**
Call `generate_outbreak_briefing(pathogen="h5n1")` live.
Show Claude generating the situational brief in real time:
> "H5N1 spillover risk is elevated across 7 tiles in Vietnam and Cambodia.
> The primary driver is migratory waterfowl corridor overlap with live poultry
> market density... Recommend: notify APSED regional focal points..."

**1:45–2:30 — Explainability**
Call `explain_risk_drivers(tile_id="AT_southeast_asia_22_8", pathogen="h5n1")` live.
Show Claude translating SHAP values into ground-level conditions and 3 specific actions.

**2:30–3:00 — Integration**
Call `get_risk_score(tile_id=..., pathogen="h5n1", fhir_format=true)`.
Show FHIR RiskAssessment resource — drop straight into clinical system.
> "Standards-compliant. Ready for EHR integration on day one."

---

## Pathogens

| ID | Display | SNOMED | Region |
|---|---|---|---|
| ebola | Ebola Virus Disease | 37109004 | Africa (Sahel, Horn) |
| h5n1 | Avian Influenza H5N1 | 396425006 | Global |
| cchfv | Crimean-Congo Haemorrhagic Fever | 19065005 | Eastern Europe |
| wnv | West Nile Virus Disease | 417093003 | Europe |
| sea-cov | SARS-CoV-2 | 840539006 | Southeast Asia |
| mpox | Mpox (Monkeypox) | 50811000 | Central / West Africa (Clade I/II), Europe |

---

## Value Proposition for Darena Health / Prompt Opinion

AqtaBio demonstrates Prompt Opinion's core thesis: multi-agent composition converts
specialist intelligence into actionable workflows.

- **Clinicians** query regional outbreak risk directly from their AI workspace
- **PHOs** compose AqtaBio with clinical agents for end-to-end pandemic preparedness
- **Healthcare AI developers** build on top of AqtaBio's risk data without direct API access
- **EHR systems** receive FHIR-native resources with zero transformation overhead

This is exactly the "Last Mile" use case: converting raw ML intelligence into
actionable clinical context via open standards (MCP + A2A + FHIR).

Validated proof: AqtaBio's model scored 0.82 on Hubei Province in November 2019 —
**53 days before the WHO was notified** that COVID-19 existed.
