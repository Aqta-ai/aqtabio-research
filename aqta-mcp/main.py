"""
FastAPI entrypoint for AqtaBio Pandemic Risk MCP Server.

Mounts the MCP Streamable HTTP handler for Prompt Opinion compatibility.
  - POST /mcp           → Streamable HTTP MCP endpoint
  - GET /.well-known/agent.json  → A2A v1.0 agent card (discovery)
  - GET /healthz        → simple health check for uptime monitors
  - GET /info           → human-readable JSON index for drive-by visitors
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server import mcp


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="AqtaBio Pandemic Risk MCP Server",
    version="0.1.0",
    lifespan=lifespan,
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
        "Pre-etiologic zoonotic disease spillover early warning system. "
        "Predicts pandemic risk 53 days before WHO notification using "
        "XGBoost + SHAP + Claude AI. Operational across 5 priority pathogens "
        "(Ebola, H5N1, CCHF, West Nile, SARS-CoV-2). Returns HL7 FHIR R4 resources."
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
        "extensions": ["ai.promptopinion/fhir-context"],
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
            "description": "Claude generates a PHO situational brief synthesising hotspots, top tiles, and SHAP drivers into an actionable narrative with 3 recommended actions. Addresses the hackathon 'AI Factor' criterion.",
            "tags": ["genai", "narrative"],
        },
        {
            "name": "explain_risk_drivers",
            "description": "Claude translates SHAP values into plain-English causal narrative for a tile, with 2-3 specific recommended actions.",
            "tags": ["genai", "explainability"],
        },
        {
            "name": "retrospective_validation",
            "description": "Returns historical risk scores + WHO notification dates for 6 validated spillover events. Makes the '53 days before WHO' COVID-19 claim live-testable as a tool call.",
            "tags": ["validation", "evidence"],
        },
        {
            "name": "get_multi_pathogen_hotspots",
            "description": "Detects syndemic convergence — regions/time windows where multiple pathogens simultaneously cross HIGH+ severity, flagging response infrastructure saturation risk.",
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
    ],
    "pathogens_covered": [
        {"id": "ebola", "display": "Ebola Virus Disease", "snomed": "37109004", "status": "operational"},
        {"id": "h5n1", "display": "Avian Influenza H5N1", "snomed": "396425006", "status": "operational"},
        {"id": "cchfv", "display": "Crimean-Congo Haemorrhagic Fever", "snomed": "19065005", "status": "operational"},
        {"id": "wnv", "display": "West Nile Virus Disease", "snomed": "417093003", "status": "operational"},
        {"id": "sea-cov", "display": "SARS-CoV-2", "snomed": "840539006", "status": "operational"},
        {"id": "mpox", "display": "Mpox (Monkeypox)", "snomed": "50811000", "status": "pilot"},
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


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return JSONResponse({"status": "ok", "service": "aqta-mcp", "version": "0.1.0"})


@app.get("/info", include_in_schema=False)
async def info():
    """Human-readable JSON index for drive-by visitors."""
    return JSONResponse({
        "service": "AqtaBio Pandemic Risk MCP Server",
        "version": "0.1.0",
        "tools": 11,
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
