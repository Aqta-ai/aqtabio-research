# Changelog

This changelog establishes a public, dated record of when each
component of the AqtaBio MCP server entered the public mirror. Entries
are append-only and timestamped at the date the corresponding commit
was pushed to `main`. Cite the relevant entry when referencing prior
work.

The canonical record is the git commit history of this repository
(`git log --follow <path>`). Entries below are a human-readable
summary of the same information.

---

## 2026-05-08

**Added** — `optimise_sentinel_placement` MCP tool, `aqta-mcp/server.py`.

  Active-learning recommender for sentinel surveillance placement.
  Given a region, pathogens of concern, the agency's existing
  sentinel sites, and the number of new sites the budget allows,
  returns a ranked deployment plan. Ranking objective:

      eig_score(t) = 0.40 · risk(t)
                   + 0.40 · uncertainty(t)        # P90 - P10
                   + 0.20 · coverage_gap(t)        # 1 - exp(-d/300km)

  Greedy selection with spread penalty `1 - exp(-d/300km)` applied
  after each pick. Documented as a tractable proxy for full
  Bayesian active learning by disagreement; v0.2.0 (target Q3 2026
  medRxiv) replaces with a proper variance-of-disagreement
  estimator across the per-pathogen XGBoost ensemble.

  Buyer profile in the docstring: Africa CDC, ECDC, USAID,
  IHR-SEA, GAVI, WHO GOARN. The formula and limitations are
  returned in every tool response so downstream callers can
  replicate the math without reading the source.

  Source: [`aqta-mcp/server.py`](aqta-mcp/server.py).

**Added** — `submit_to_hapi_fhir` made idempotent on (pathogen, tile_id).

  Strips client-supplied `id` from the FHIR R4 resource before
  POST (FHIR R4: server assigns ids; client ids on POST are
  non-portable and trigger HAPI's strict-mode rejection). On HAPI
  HTTP 412, parses the existing resource id from the
  OperationOutcome diagnostics (`HAPI-2840: Can not create resource
  duplicating existing resource: RiskAssessment/<id>`) and returns
  it with `hapi_status: 200`. Idempotent within HAPI's ~30 day
  persistence window.

**Added** — Reference Python agent and no-key smoke test.

  - `aqta-mcp/adk_briefing_agent.py` — Google ADK + Gemini wrapper
    that composes the MCP tool surface into a sentinel-placement
    flow. ADK path with google-genai fallback for environments
    where ADK is not yet installed.
  - `aqta-mcp/smoke_test_mcp_flow.py` — no-key end-to-end test;
    exercises tools/list, optimise_sentinel_placement, get_risk_score
    with FHIR R4 output, submit_to_hapi_fhir round-trip.

**Added** — `aqta-mcp/MCP_USAGE.md` paste-ready curl examples that
include the required `Accept: application/json, text/event-stream`
header.

**Removed** — `docs/research/preprint-outline.md` (was a working draft
with placeholder slots; pre-empted the eventual medRxiv submission).

**Removed** — `docs/research/RESEARCHER_GUIDE.md` and
`docs/research/API_EXAMPLES.md` (exposed an internal access code and
referenced legacy authentication endpoints).

**Removed** — `aqta-mcp/agent-config.md` (stale tool counts, internal
pitch material; the legitimate parts now live in MCP_USAGE.md with
honest framing).

---

## 2026-04-30

**Added** — `scripts/verify_mcp.py` (five-step MCP smoke test).

(Initial sync prior to the May refactor; see git history for detail.)

---

## 2026-04-29

**Added** — `docs/SECURITY.md` (vulnerability disclosure + closed/open
boundary).

---

## 2026-04-28

**Added** — `get_disease_x_risk` MCP tool (pathogen-agnostic spillover
score across the eight priority pathogens via probabilistic union).

**Added** — `data/recorded-attestations.json` (citable historical
spillover anchors with publicly verifiable WHO / ECDC notification
dates).

---

## 2026-04-27

**Initial commit** — AqtaBio v0.1.0 research artefacts.

  XGBoost + SHAP per-pathogen models, the 25-event historical cohort
  definition, the 8-layer governance framework, the EU AI Act
  Annex III §5(a) classification + 12-month conformity roadmap, and
  the public MCP server source.
