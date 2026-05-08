# AqtaBio MCP — usage guide

Live endpoint: `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp`

Public, no authentication required. Streamable HTTP transport per the
MCP specification. Server-Sent Events response shape.

---

## ⚠ Critical: set `Accept: application/json, text/event-stream`

The server uses streamable HTTP, which requires the client to accept
`text/event-stream` for the response. A `curl` or HTTP client that
does not include this header gets the following error and reads as
"server broken":

```json
{
  "jsonrpc": "2.0",
  "id": "server-error",
  "error": {
    "code": -32600,
    "message": "Not Acceptable: Client must accept text/event-stream"
  }
}
```

**This is the client's problem, not the server's.** Add the `Accept`
header and the call works. Every example below sets the header
correctly.

---

## Discover the tools

```bash
curl -X POST https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Expected: 19 tools across spillover-risk lookup, FHIR R4 emission,
retrospective validation, multi-pathogen syndemic detection,
sentinel-placement recommendation, and a self-test orchestrator.

---

## Sentinel-placement recommendation

Active-learning recommender for public-health agencies operating
under a finite surveillance budget. Returns a ranked deployment
plan with expected information gain per tile.

```bash
curl -X POST https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "optimise_sentinel_placement",
      "arguments": {
        "pathogens": ["ebola", "h5n1"],
        "region": "africa-cdc",
        "budget_sites": 10
      }
    }
  }'
```

Method (returned in every response): `eig_score = 0.40·max_risk +
0.40·(P90-P10) + 0.20·coverage_gap`, with a greedy-selection spread
penalty `1 - exp(-d/300km)` so the recommended set does not cluster.
This is a tractable proxy for full Bayesian active learning by
disagreement; v0.2.0 (Q3 2026 medRxiv) replaces with a proper
variance-of-disagreement estimator across the per-pathogen XGBoost
ensemble.

---

## Per-pathogen risk score with FHIR R4

```bash
curl -X POST https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_risk_score",
      "arguments": {
        "tile_id": "AS-025-45678",
        "pathogen": "sea-cov",
        "fhir_format": true
      }
    }
  }'
```

Returns a FHIR R4 `RiskAssessment` resource with the risk score,
confidence band, top SHAP feature drivers, and SNOMED CT pathogen
code.

---

## Live HAPI FHIR round-trip

POST a real `RiskAssessment` to the public HAPI FHIR test server
and get back a queryable URL. Idempotent on (pathogen, tile_id):
repeat calls return the existing resource id rather than failing
on duplicate.

```bash
curl -X POST https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "submit_to_hapi_fhir",
      "arguments": {
        "tile_id": "AS-025-45678",
        "pathogen": "sea-cov"
      }
    }
  }'
```

Then verify the resource directly on HAPI:

```bash
curl -H "Accept: application/fhir+json" \
  https://hapi.fhir.org/baseR4/RiskAssessment/<resource_id>
```

---

## Retrospective validation

Returns the recorded retrospective attestation for a historical
spillover event paired with the publicly verifiable WHO / ECDC /
national notification date. NOT a live model recomputation; the
`cross_check` field on the response surfaces the v0.1.0 backtest
provenance and AUROC / AUCPR / hit-rate.

```bash
curl -X POST https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "retrospective_validation",
      "arguments": {
        "event_id": "2019_wuhan_sars_cov_2"
      }
    }
  }'
```

Anchor events available: `2019_wuhan_sars_cov_2`, `2022_mpox_global`,
`2014_west_africa_ebola`, `2018_drc_ebola`, `2018_wnv_italy`,
`2018_cchfv_turkey`, `2023_marburg_equatorial_guinea`,
`2018_lassa_nigeria`.

---

## Self-test (every tool, sane defaults)

```bash
curl -X POST https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"self_test","arguments":{}}}'
```

Returns per-tool pass/fail. Use as a CI heartbeat or pre-demo check.

---

## Connect from an MCP client

Any MCP-aware client works (Claude Desktop, MCP-aware clinician
workspaces, your own Python ADK + Gemini agent, etc.). Server
transport metadata:

- **Transport**: Streamable HTTP per the MCP spec
- **URL**: `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp`
- **Extension**: `ai.promptopinion/fhir-context` declared in capabilities
- **A2A v1.0 agent card**: `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/.well-known/agent.json`

A reference Python agent (Google ADK + Gemini) is provided in
[`adk_briefing_agent.py`](adk_briefing_agent.py); a no-key smoke test
in [`smoke_test_mcp_flow.py`](smoke_test_mcp_flow.py).

---

## Pathogens covered

8 priority pathogens: Ebola Virus Disease, Avian Influenza H5N1,
Crimean-Congo Haemorrhagic Fever, West Nile Virus Disease,
SARS-CoV-2, Mpox, Nipah Virus, Hantavirus.

Five (Ebola, H5N1, CCHF, West Nile, SARS-CoV-2) have seeded
production tile predictions in v0.1.0; three (Mpox, Nipah,
Hantavirus) are trained but pending tile seeding. The
`prediction_status` field on `list_pathogens` returns the canonical
state.

SNOMED CT codes per pathogen are returned by `list_pathogens` and
embedded in every FHIR `RiskAssessment` resource.

---

## Honest framing of the model

AqtaBio is a pre-etiologic spillover risk service. It scores the
probability that a 25 km tile's environmental, ecological, and
demographic state matches the pattern that historically appeared
*before* known zoonotic spillover events. It does not predict the
specific pathogen or the specific date; the recorded retrospective
attestations are backtest results frozen at v0.1.0 development
time, not live 2019 forecasts.

The model's claims and limits live in
[`docs/research/known-limitations.md`](../docs/research/known-limitations.md)
and [`docs/research/VALIDATION_METHODOLOGY.md`](../docs/research/VALIDATION_METHODOLOGY.md).

The aggregate AUROC, AUCPR, and lead-time distribution across the
full 25-event historical cohort is the deliverable of the medRxiv
preprint; target Q3 2026.
