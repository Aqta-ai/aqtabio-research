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

## 2026-05-08 (Prompt Opinion submission)

**Added** — `aqta-mcp/promptopinion-submission.md`.

  Standalone submission doc for the Prompt Opinion clinician
  workspace. Covers the SHARP context propagation contract
  (`patient_id`, `encounter_id`, `fhir_server`, `access_token`),
  the two SHARP-aware tools (`get_patient_local_risk` and
  `emit_riskassessment_to_ehr`), the PHI minimisation argument
  (only `address.country` is retained), and the dry-run default
  on EHR write-back. Live curl examples included.

**Hardened** — `emit_riskassessment_to_ehr` defaults to dry-run.

  Previously the tool POSTed to the SHARP-supplied `fhir_server`
  on a single RPC, which means a mis-configured workspace could
  accidentally write to a real production EHR. Now the default
  behaviour returns the resource that *would* be written under
  `dry_run_resource` along with `would_post_to` and a
  `fhir_host_is_known_sandbox` flag (sandbox allowlist:
  `hapi.fhir.org`, `server.fire.ly`, `spark.incendi.no`,
  `fhir.smarthealthit.org`). The caller must pass
  `confirm_write: true` to actually POST. Writes to non-sandbox
  hosts are accepted but the response surfaces
  `wrote_to_non_sandbox_host: true` so the workspace can audit
  the action. The bearer token from the SHARP block continues to
  be forwarded verbatim and is never stored on the AqtaBio side.

  Source: [`aqta-mcp/server.py`](aqta-mcp/server.py).

  Live image pinned to immutable tag `aqta-mcp:v0.1.1-promptopinion`
  (digest `sha256:1679d0fcceff3c1a7a62140ccea015a0f6a9e868ced97212c
  c6768dffebf0f6f`). App Runner service redeployed against the
  versioned tag.

---

## 2026-05-08 (later, again)

**Renamed** — `/auth/judge-token` and `/auth/judge-exchange` to
`/auth/evaluator-token` and `/auth/evaluator-exchange`.

  The old route names ship of "judge" framing that conflated
  hackathon-judging with the actual user role (a public-health
  responder evaluating predictions). The new names match the
  dashboard's preview-access cookie naming and the public-mirror
  README's "evaluator" terminology. Request body field on the
  exchange endpoint renamed `judge_token` → `evaluator_token`.

  Backwards compatibility: env vars `EVALUATOR_SESSION_SECRET` and
  `EVALUATOR_ACCESS_CODE` are read first, with `JUDGE_SESSION_SECRET`
  and `JUDGE_ACCESS_CODE` retained as fallback so the existing Lambda
  env keeps working through the rotation window. The role string
  "evaluator" is used for newly minted users; "judge" remains in the
  `allowed_roles` set so legacy DB rows continue to validate.

**Fixed** — `/health.data_freshness_hours` returned the 999.0 sentinel
even when the prediction pipeline was current.

  Root cause: the metric was computed from `MAX(features.as_of_date)`,
  but `features.as_of_date` is a feature-engineering target date
  (often a future calendar boundary), not a wall-clock ingestion
  stamp. The aggregate either returned NULL or a far-future date and
  the response collapsed to the default. Now reads
  `MAX(computed_at) FROM tile_predictions`; falls back to
  `MAX(features.as_of_date)` only if no predictions have been
  computed yet. The per-tile `data_freshness` field on tile-risk
  responses is also now the row's real `computed_at` instead of
  `datetime.utcnow()`.

---

## 2026-05-08 (later)

**Added** — `2018_lassa_nigeria` anchor event in `retrospective_validation`.

  Eighth historical anchor on the live MCP. Edo / Ondo / Ebonyi
  states, Nigeria; threshold-crossing 2017-11-12 at score 0.73;
  Nigeria CDC outbreak declaration 2018-01-22; lead time 71 days.
  Drivers: mastomys rodent density, household grain storage proxy,
  rainfall anomaly, healthcare access index. Source-of-truth date
  is the Nigeria CDC declaration; cross-checkable against the 2018
  WHO Disease Outbreak News for Lassa fever Nigeria.

**Hardened** — Live MCP image pinned to immutable tag.

  App Runner service `aqta-mcp` (eu-west-1) switched from
  `aqta-mcp:latest` to `aqta-mcp:v0.1.0-submission` in ECR. The
  manifest digest is locked at `sha256:a8031e5132ac4a1e51e481ca14b66
  25338cf024efafee03f309706b235dd1f35`. An accidental push to
  `:latest` can no longer change what the public live endpoint
  serves. A local tarball backup of the same digest is held offline.

**Cleaned** — Removed overclaim language from `/.well-known/agent.json`.

  The agent card description previously read "Predicts pandemic
  risk 53 days before WHO notification". Replaced with the
  backtest-honest framing that already appears in the README:
  per-pathogen ebola backtest AUROC up to 0.975 on held-out
  time-aware splits, with aggregate AUROC / AUCPR / lead-time
  distribution across the full 25-event cohort tracked as the
  forthcoming medRxiv preprint deliverable. The same correction
  was applied to the `retrospective_validation` skill description.

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
