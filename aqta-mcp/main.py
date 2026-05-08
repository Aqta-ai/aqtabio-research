"""
FastAPI entrypoint for AqtaBio Pandemic Risk MCP Server.

Mounts the MCP Streamable HTTP handler for Prompt Opinion compatibility.
  - POST /mcp           → Streamable HTTP MCP endpoint
  - GET /.well-known/agent.json  → A2A v1.0 agent card (discovery)
  - GET /healthz        → simple health check for uptime monitors
  - GET /info           → human-readable JSON index for drive-by visitors
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server import mcp


# Lifespan is wired below via @app.on_event("startup"/"shutdown") so that
# BOTH the SSE and Streamable HTTP subapps' session managers come up.
# Don't pass `lifespan=` here — doing so would invoke
# `mcp.session_manager.run()` a second time (the streamable_http subapp's
# lifespan_context already runs it), and StreamableHTTPSessionManager.run()
# is one-shot per instance.
app = FastAPI(
    title="AqtaBio Pandemic Risk MCP Server",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# A2A v1.0 Agent Card — agent discovery endpoint (RFC 8615 well-known URI).
# https://a2a-protocol.org/latest/specification/
# Declared BEFORE app.mount("/") so FastAPI routes it before falling through
# to the MCP handler.
# ---------------------------------------------------------------------------
_AGENT_CARD = {
    "name": "AqtaBio Pandemic Risk Agent",
    "description": (
        "Pre-etiologic zoonotic spillover risk forecasting at 25 km tile "
        "resolution. Backtest validation on the v0.1.0 historical cohort: "
        "AUROC up to 0.975 on held-out time-aware splits for ebola "
        "(per-pathogen, see reports/ebola/backtest_validation.json in the "
        "closed source). Aggregate AUROC, AUCPR, and lead-time distribution "
        "across the full 25-event cohort is the deliverable of the "
        "forthcoming medRxiv preprint (target Q3 2026); this system is not "
        "yet prospectively validated. Covers 8 priority pathogens from the "
        "WHO R&D Blueprint Disease X candidate set: 5 producing live tile "
        "predictions in production (Ebola, H5N1, CCHF, West Nile, SARS-CoV-2) "
        "and 3 with trained models pending tile seeding (Mpox, Nipah, "
        "Hantavirus). Hantavirus was added on 2026-05-04 in response to "
        "early reports of the South Atlantic cruise outbreak; WHO confirmed "
        "the cluster on 2026-05-06 (8 cases, 3 lab-confirmed Andes strain). "
        "Pathogen onboarding (schema, training, bundled model, agent card) "
        "ran end-to-end in hours. Tile seeding for hantavirus is still in "
        "progress, so this case demonstrates operational responsiveness, "
        "not predictive lead time. The 5 live pathogens are trained on GZOD "
        "historical spillover labels; the 3 pending pathogens are trained on "
        "epidemiologically-grounded synthetic labels (same standard as MenB) "
        "pending real-label retraining for the Q3 2026 medRxiv preprint. "
        "See `prediction_status` and the training-script citations on each "
        "entry. Exposes 19 callable tools including active-learning sentinel "
        "placement (`optimise_sentinel_placement`), pathogen-agnostic "
        "Disease X scoring, counterfactual hindcasting, live HL7 FHIR R4 "
        "round-trip submission to public HAPI (idempotent on pathogen+tile), "
        "full SHARP context support (Prompt Opinion "
        "`ai.promptopinion/fhir-context` extension), and a self_test tool "
        "that runs every other tool end-to-end and returns a structured "
        "pass/fail map for CI verification."
    ),
    "version": "0.1.0",
    # Top-level url is REQUIRED by the A2A v1.0 AgentCard schema. Clients that
    # auto-discover via /.well-known/agent.json (Prompt Opinion among them)
    # read this field to know where to call. Omitting it makes
    # `jq '.url'` return null and silently breaks agent-discovery flows even
    # though the rest of the card is well-formed.
    "url": "https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp",
    "protocol_version": "1.0",
    "protocolVersion": "1.0",  # camelCase alias per A2A v1.0 JSON representation
    "provider": {
        "organization": "Aqta Technologies Limited",
        "url": "https://aqtabio.org",
    },
    "model_info": {
        "primary": "claude-haiku-4-5-20251001",
        "scoring": "XGBoost + SHAP v0.1.0",
        "training_cutoff": "2025-10-01",
    },
    "service_endpoint": "https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp",
    "supported_protocols": ["mcp-streamable-http", "http+json/rest"],
    "authentication": {
        "type": "none",
        "description": "Public read-only tooling. Rate limits enforced upstream.",
    },
    "capabilities": {
        "streaming": True,
        "fhir_r4": True,
        "prediction_status_taxonomy": (
            "pathogens_covered entries carry a `prediction_status` field: "
            "'live' = tile_predictions rows exist in production; "
            "'pending_tile_seeding' = XGBoost model bundled but atlas tiles "
            "not yet seeded, so the prediction pipeline has not run."
        ),
        "extensions": ["ai.promptopinion/fhir-context"],
        "sharp_context": {
            "supported": True,
            "fields_consumed": ["patient_id", "encounter_id", "fhir_server", "access_token"],
            "tools_using_sharp": ["get_patient_local_risk", "emit_riskassessment_to_ehr"],
            "phi_minimisation": (
                "Only address.country is retained from the FHIR Patient "
                "resource. Risk is population-level (25 km tile). No patient "
                "identifier, name, DOB, or condition is stored or returned."
            ),
        },
    },
    "skills": [
        {
            "name": "list_pathogens",
            "description": "List all monitored pathogens with SNOMED CT codes and geographic scope.",
            "tags": ["discovery"],
        },
        {
            "name": "get_risk_score",
            "description": "Current spillover risk score for a geographic tile with SHAP feature drivers. FHIR RiskAssessment optional.",
            "tags": ["query", "fhir"],
        },
        {
            "name": "get_hotspots",
            "description": "Hotspot counts by severity tier (critical ≥0.9, high ≥0.7, moderate ≥0.5) for a pathogen. FHIR DetectedIssue optional.",
            "tags": ["query", "fhir", "aggregate"],
        },
        {
            "name": "get_risk_trend",
            "description": "24-month risk trajectory for a tile. FHIR Observation Bundle optional.",
            "tags": ["query", "timeseries", "fhir"],
        },
        {
            "name": "get_top_risk_tiles",
            "description": "Highest-risk tiles ranked by score for a pathogen.",
            "tags": ["query", "ranking"],
        },
        {
            "name": "get_system_status",
            "description": "System health, data freshness, live vs demo mode.",
            "tags": ["ops"],
        },
        {
            "name": "generate_outbreak_briefing",
            "description": "Claude generates a PHO situational brief synthesising hotspots, top tiles, and SHAP drivers into an actionable narrative with 3 recommended actions.",
            "tags": ["genai", "narrative"],
        },
        {
            "name": "explain_risk_drivers",
            "description": "Claude translates SHAP values into plain-English causal narrative for a tile, with 2-3 specific recommended actions.",
            "tags": ["genai", "explainability"],
        },
        {
            "name": "retrospective_validation",
            "description": "Returns the recorded retrospective attestation for a historical spillover event paired with the publicly verifiable WHO / ECDC / national notification date. Backtest provenance, AUROC and AUCPR are surfaced in the `cross_check` field. Not a live model recomputation.",
            "tags": ["validation", "evidence"],
        },
        {
            "name": "get_multi_pathogen_hotspots",
            "description": "Detects syndemic convergence: regions and time windows where multiple pathogens simultaneously cross HIGH+ severity, flagging response infrastructure saturation risk.",
            "tags": ["syndemic", "aggregate"],
        },
        {
            "name": "generate_fhir_bundle_for_pho",
            "description": "Complete HL7 FHIR R4 transaction Bundle (RiskAssessment + DetectedIssue + 12×Observation) with per-entry POST requests, ready to submit to any FHIR server.",
            "tags": ["fhir", "integration"],
        },
        {
            "name": "get_disease_x_risk",
            "description": "Pathogen-agnostic pre-spillover risk score addressing the WHO R&D Blueprint's Disease X priority. Aggregates per-pathogen risks into a single 'any zoonotic emergence' signal for the unknown pathogen of the next pandemic.",
            "tags": ["disease-x", "blueprint", "novel"],
        },
        {
            "name": "get_hindcast",
            "description": "Counterfactual timeline analysis. Given a recorded retrospective attestation, returns the actual outbreak timeline alongside an illustrative counterfactual: what intervention window would have been available if a public-health responder had acted N days after the threshold-crossing signal. Honest about caveats; no claim of cases averted.",
            "tags": ["counterfactual", "validation", "novel"],
        },
        {
            "name": "submit_to_hapi_fhir",
            "description": "Live HL7 FHIR R4 round-trip: builds a RiskAssessment for a tile/pathogen/month, POSTs to the public HAPI FHIR test server, and returns the assigned resource URL plus HAPI's HTTP status. Makes the 'FHIR round-trip tested' claim a callable proof; anyone can fetch the resource back to verify conformance. Population-level risk only, no PHI.",
            "tags": ["fhir", "interop", "verifiable"],
        },
        {
            "name": "get_patient_local_risk",
            "description": "SHARP-aware patient-local risk. Reads the Prompt Opinion `ai.promptopinion/fhir-context` block (patient_id, fhir_server, access_token), fetches the Patient resource via SMART-on-FHIR, derives the home tile from address.country, and returns AqtaBio's population-level spillover risk for that area. PHI minimisation: only country is retained. Designed to be invoked from a clinician's Prompt Opinion workspace.",
            "tags": ["sharp", "fhir", "patient-context", "smart-on-fhir"],
        },
        {
            "name": "emit_riskassessment_to_ehr",
            "description": "SHARP-aware EHR write-back. Takes the SHARP-propagated bearer token from the clinician's EHR session and POSTs an AqtaBio FHIR RiskAssessment resource to the same FHIR server, attached to the patient reference. Demonstrates round-trip context propagation: the platform's promise of bridging EHR credentials without bespoke token handling is verifiable end-to-end.",
            "tags": ["sharp", "fhir", "writeback", "smart-on-fhir"],
        },
        {
            "name": "handoff_to_triage",
            "description": "A2A v1.0 handoff. Takes a FHIR RiskAssessment from the surveillance side of AqtaBio and returns a FHIR Task that hands the matter to a clinical triage specialist agent. The Task carries a deterministic risk-band action (notify / surveil / routine) plus a disclaimer in note that the mapping is not clinical decision support; a public health officer must approve before any operational step. The triage specialist agent card is exposed at /.well-known/triage-agent.json.",
            "tags": ["a2a", "handoff", "fhir", "task", "triage"],
        },
        {
            "name": "self_test",
            "description": "Runs every other tool with sane default arguments and returns a structured pass/fail map. Lets CI / pre-deploy / post-deploy check that all 16 working tools execute without exception. Catches dangling references and missing pathogen branches that would otherwise only surface in a clinician's workspace.",
            "tags": ["self-test", "ci", "ops"],
        },
    ],
    "pathogens_covered": [
        # `model_status` is "trained" when a dedicated XGBoost + SHAP model
        # is bundled at models/{id}/model.ubj, and "training" when the
        # pathogen schema and ecological feature pipeline are wired but the
        # dedicated classifier has not yet been trained — in which case the
        # score falls back to the calibrated heuristic. Both states are
        # surfaced honestly so downstream callers can choose how to weight
        # the signal.
        {"id": "ebola", "display": "Ebola Virus Disease", "snomed": "37109004", "status": "operational", "model_status": "trained", "prediction_status": "live"},
        {"id": "h5n1", "display": "Avian Influenza H5N1", "snomed": "396425006", "status": "operational", "model_status": "trained", "prediction_status": "live"},
        {"id": "cchfv", "display": "Crimean-Congo Haemorrhagic Fever", "snomed": "19065005", "status": "operational", "model_status": "trained", "prediction_status": "live"},
        {"id": "wnv", "display": "West Nile Virus Disease", "snomed": "417093003", "status": "operational", "model_status": "trained", "prediction_status": "live"},
        {"id": "sea-cov", "display": "SARS-CoV-2", "snomed": "840539006", "status": "operational", "model_status": "trained", "prediction_status": "live"},
        {"id": "mpox", "display": "Mpox (Monkeypox)", "snomed": "50811000", "status": "operational", "model_status": "trained", "prediction_status": "pending_tile_seeding"},
        {"id": "nipah", "display": "Nipah Virus", "snomed": "27332006", "status": "operational", "model_status": "trained", "prediction_status": "pending_tile_seeding"},
        {"id": "hantavirus", "display": "Hantavirus", "snomed": "16541001", "status": "operational", "model_status": "trained", "prediction_status": "pending_tile_seeding"},
    ],
    "validation_claim": {
        "event": "COVID-19 Wuhan",
        "model_prediction_date": "2019-11-08",
        "risk_score": 0.82,
        "who_notification_date": "2019-12-31",
        "lead_time_days": 53,
        "tile_id": "AS-025-45678",
        "verifiable_via": "retrospective_validation(event_id='2019_wuhan_sars_cov_2')",
    },
    "documentation_url": "https://aqtabio.org/proof-of-concept",
}


@app.get("/.well-known/agent.json", include_in_schema=False)
async def agent_card():
    """A2A v1.0 Agent Card — served at the RFC 8615 well-known URI."""
    return JSONResponse(_AGENT_CARD, headers={"Cache-Control": "public, max-age=300"})


@app.get("/.well-known/agent-card.json", include_in_schema=False)
async def agent_card_alias():
    """Alias — some A2A client libraries look at `agent-card.json`."""
    return JSONResponse(_AGENT_CARD, headers={"Cache-Control": "public, max-age=300"})


# ---------------------------------------------------------------------------
# Triage specialist agent card. Second A2A endpoint in this same service so
# a downstream Prompt Opinion or A2A peer can discover it without spinning
# a separate deploy. Triage skills are deliberately narrow: take a Task
# produced by the surveillance side, present it to a public health officer,
# and (post-approval) carry it forward.
# ---------------------------------------------------------------------------
_TRIAGE_AGENT_CARD = {
    "name": "AqtaBio Clinical Triage Specialist",
    "description": (
        "A2A specialist agent that consumes FHIR Task resources produced by "
        "the AqtaBio surveillance agent's handoff_to_triage tool. The Task "
        "carries a deterministic risk-band action (urgent notification, "
        "enhanced surveillance, or routine monitoring) plus an explicit "
        "disclaimer that the mapping is not clinical decision support. The "
        "triage specialist surfaces that Task to a public health officer "
        "via the approval workspace at https://aqtabio.org/triage, "
        "captures Approve / Amend / Reject with reviewer attribution, and "
        "(v0.2) forwards approved actions to the consuming system "
        "(notification queue, EHR write-back via FHIR Task.executionPeriod, "
        "sentinel placement workflow). v0.1.0: card exposed for discovery, "
        "browser-based approval workspace live, decisions persist in "
        "localStorage for the reviewing session. v0.2.0: server-side "
        "decision log + EHR write-back."
    ),
    "url": "https://qjtqgvpd9s.eu-west-1.awsapprunner.com",
    "protocol_version": "1.0",
    "preferred_transport": "streamable_http",
    "capabilities": {
        "streaming": True,
        "tools": False,
        "a2a_handoff": {
            "supported": True,
            "accepts_handoff_from": [
                "AqtaBio Pandemic Risk Agent",
            ],
            "consumes_resource_types": ["Task"],
            "approval_workspace_url": "https://aqtabio.org/triage",
            "task_url_template": (
                "https://aqtabio.org/triage?task={base64-encoded-FHIR-Task-JSON}"
            ),
            "decision_outcomes": ["approved", "amended", "rejected"],
            "v0_1_status": (
                "Card exposed for discovery, browser-based approval "
                "workspace live, decisions persist in localStorage."
            ),
            "v0_2_roadmap": (
                "Server-side decision log + EHR FHIR Task.executionPeriod "
                "write-back + notification-queue forward."
            ),
        },
    },
    "skills": [],
    "license": "MIT",
    "contact": {
        "name": "Aqta Technologies Limited",
        "url": "https://aqtabio.org",
        "email": "hello@aqta.ai",
    },
}


@app.get("/.well-known/triage-agent.json", include_in_schema=False)
async def triage_agent_card():
    """Second A2A v1.0 Agent Card for the clinical triage specialist."""
    return JSONResponse(_TRIAGE_AGENT_CARD, headers={"Cache-Control": "public, max-age=300"})


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return JSONResponse({"status": "ok", "service": "aqta-mcp", "version": "0.1.0"})


@app.get("/info", include_in_schema=False)
async def info():
    """Human-readable JSON index for drive-by visitors."""
    return JSONResponse({
        "service": "AqtaBio Pandemic Risk MCP Server",
        "version": "0.1.0",
        "tools": len(_AGENT_CARD["skills"]),
        "transport": "MCP Streamable HTTP",
        "endpoints": {
            "mcp": "POST /mcp",
            "agent_card": "GET /.well-known/agent.json",
            "health": "GET /healthz",
        },
        "tool_names": [s["name"] for s in _AGENT_CARD["skills"]],
        "documentation": "https://aqtabio.org/mcp",
    })


# Dual MCP transport so older AND newer clients both connect:
#
#   POST /mcp         — Streamable HTTP (MCP 2025-03-26+, current spec).
#                       Used by Claude Desktop, mcp-inspector, recent
#                       Prompt Opinion versions.
#   GET  /sse         — legacy SSE channel (MCP 2024-11-05 spec).
#   POST /messages/   — legacy paired POST endpoint.
#                       Used by older Prompt Opinion clients and any MCP
#                       integration written before the Streamable HTTP
#                       unification.
#
# Implementation note: the naive `app.mount("/", subapp)` for both fails
# because Starlette dispatches the FIRST matching mount-prefix, so the
# second subapp is unreachable. Instead we extract individual routes
# from each subapp and append them to the main app's router. Each
# subapp's lifespan_context (which starts the MCP session manager that
# the routes depend on) is wired into FastAPI's startup/shutdown hooks
# so both managers are running when requests arrive.
import contextlib  # noqa: E402

_sse_subapp = mcp.sse_app()
_streamable_subapp = mcp.streamable_http_app()

for _route in _sse_subapp.router.routes:
    app.router.routes.append(_route)
for _route in _streamable_subapp.router.routes:
    app.router.routes.append(_route)


@app.on_event("startup")
async def _start_mcp_session_managers():
    """Bring up both transports' MCP session managers."""
    app.state._mcp_lifespan_cms = []
    for sub in (_sse_subapp, _streamable_subapp):
        ctx_factory = sub.router.lifespan_context
        if ctx_factory is None:
            continue
        # Starlette's lifespan_context is a callable; passing the subapp
        # returns the async context manager.
        cm = ctx_factory(sub)
        await cm.__aenter__()
        app.state._mcp_lifespan_cms.append(cm)


@app.on_event("shutdown")
async def _stop_mcp_session_managers():
    for cm in reversed(getattr(app.state, "_mcp_lifespan_cms", [])):
        try:
            await cm.__aexit__(None, None, None)
        except Exception:  # nosec: shutdown best-effort
            pass
