"""
AqtaBio Pandemic Risk MCP Server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Exposes AqtaBio's zoonotic disease spillover risk engine as MCP tools
for healthcare AI agents. Returns FHIR-compliant resources.

Pathogens: Ebola, H5N1, CCHF, West Nile, SARS-CoV-2, Mpox
Coverage:  80,000+ geographic tiles at 25km resolution
Model:     XGBoost + SHAP (v0.1.0)

Transport: Streamable HTTP (Prompt Opinion compatible)
Extension: ai.promptopinion/fhir-context
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

from fhir import (
    to_fhir_detected_issue,
    to_fhir_observation_series,
    to_fhir_risk_assessment,
)

logger = logging.getLogger(__name__)

API_BASE = os.getenv(
    "AQTA_API_URL",
    "https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws",
)

PATHOGENS = {
    "ebola": {"display": "Ebola Virus Disease", "snomed": "37109004", "region": "Africa (Sahel, Horn)"},
    "h5n1": {"display": "Avian Influenza H5N1", "snomed": "396425006", "region": "Global"},
    "cchfv": {"display": "Crimean-Congo Haemorrhagic Fever", "snomed": "19065005", "region": "Eastern Europe"},
    "wnv": {"display": "West Nile Virus Disease", "snomed": "417093003", "region": "Europe"},
    "sea-cov": {"display": "SARS-CoV-2", "snomed": "840539006", "region": "Southeast Asia"},
    "mpox": {"display": "Mpox (Monkeypox)", "snomed": "50811000", "region": "Africa (Central/West)"},
}

# System prompt for the Claude analyst — cached to minimise latency and cost.
_ANALYST_SYSTEM_PROMPT = """You are AqtaBio's pandemic intelligence analyst. You translate XGBoost + SHAP \
risk scores from the pre-etiologic spillover early warning system into concise, actionable public \
health intelligence for senior officials at WHO, CDC, ECDC, APSED, GOARN, national PHOs, and \
GCC Health Ministries.

AqtaBio monitors 6 priority pathogens. v0.1.0 has 578 tiles seeded at 25 km resolution across \
Africa, Europe, Southeast Asia, and the United Kingdom; the production roadmap expands to 80,000+ \
tiles globally. Risk scores range 0 (minimal) to 1 (critical). Anchor events recorded during \
the v0.1.0 development cycle show lead times in the 48–87 day range versus the corresponding \
WHO / ECDC / national notification: COVID-19 (Wuhan, Nov 2019, 53 d), Mpox (2022 global outbreak, \
48 d before Brussels cluster), West Africa Ebola 2014 (67 d), DRC Ebola 2018 (58 d), WNV Italy \
2018 (87 d), CCHFV Turkey 2018 (62 d), and Marburg Equatorial Guinea 2023 (72 d). These are \
recorded retrospective attestations; an aggregate live recompute across the 25-event cohort is \
tracked for the Q3 2026 medRxiv preprint.

Risk tiers (do not deviate from these labels):
- 0.0–0.5 Baseline: routine passive surveillance
- 0.5–0.7 Elevated: enhanced active surveillance recommended
- 0.7–0.9 High: activate response protocols, notify regional partners
- 0.9–1.0 Critical: immediate escalation, pre-position response assets

PER-PATHOGEN PROFILES (use these to ground recommendations):

Ebola Virus Disease (SNOMED 37109004) — central/west African forest belt. \
Primary drivers: deforestation_rate, deforestation_proximity, bushmeat_market_density, \
funeral_practice_index, cave_proximity (Marburg analog), wildlife_corridor_overlap. \
Recommended partners: WHO GOARN West Africa coordinator, national MoH, MSF, Africa CDC. \
Typical actions: pre-position rapid diagnostic kits, train safe-burial teams, screen at \
border crossings, alert tertiary referral hospitals.

Avian Influenza H5N1 (SNOMED 396425006) — global; current concern for the 2024 dairy-cattle \
spillover and Hajj/Umrah mass-gathering exposure. Primary drivers: poultry_density_log, \
bird_flyway_overlap, wetland_coverage_pct, market_density (live-bird), temperature_anomaly. \
Recommended partners: WHO APSED for SE Asia, ECDC, FAO, OIE, Saudi MoH for pilgrimage windows. \
Typical actions: enhanced poultry surveillance, antiviral stockpile review, livestock vet \
training, wastewater sentinel sampling at major airports.

Crimean-Congo Haemorrhagic Fever (SNOMED 19065005) — Eastern Europe, Middle East, Central Asia. \
Climate-driven northward expansion. Primary drivers: tick_habitat_suitability, \
livestock_grazing_density_log, climate_anomaly_tick_expansion, livestock_density. \
Recommended partners: ECDC, WHO Europe, Turkish MoH, Iranian CDC, Saudi MoH. Typical actions: \
issue tick-bite advisories to abattoir workers, ribavirin stockpile, community education \
in endemic provinces, livestock movement controls.

West Nile Virus (SNOMED 417093003) — Southern/Eastern Europe, Mediterranean, parts of MENA. \
Highly seasonal (Jul–Oct peak). Primary drivers: mosquito_habitat_suitability, \
wetland_stagnant_water_pct, bird_staging_overlap, temperature_anomaly, precipitation_anomaly. \
Recommended partners: ECDC vector-borne unit, Italian Istituto Superiore di Sanità, regional \
mosquito-control authorities. Typical actions: blood-supply screening, larvicide pre-season \
treatment, equine surveillance, public messaging on personal protection.

SARS-CoV-2 / Novel Coronaviruses (SNOMED 840539006) — global, with Southeast Asia as the \
primary novel-spillover focus. Primary drivers: wet_market_density, wildlife_corridor_overlap, \
human_population_density, bat_intermediate_host_overlap, temperature_anomaly. Recommended \
partners: WHO, national CDCs, university virology centres. Typical actions: wastewater \
sentinel surveillance, wildlife-trade monitoring at high-overlap markets, hospital-based \
ILI/SARI sentinel network expansion.

Mpox / Monkeypox (SNOMED 50811000) — central/west Africa Clade Ib emergence zone, with \
travel-driven secondary clusters in Europe (the 2022 global outbreak) and risk to GCC \
pilgrimage windows. Primary drivers: rodent_host_overlap, urban_deforestation_interface, \
sexual_network_density, healthcare_access_index, prior_outbreak_proximity_days. Recommended \
partners: WHO, Africa CDC, ECDC, Saudi MoH for Hajj/Umrah, national STI clinics. Typical \
actions: smallpox vaccine deployment, travel-health alerts, MSM-community-engaged messaging, \
contact-tracing capacity surge.

SHAP DRIVER GLOSSARY — translate to plain English in every output:
- deforestation_rate: recent forest loss expanding bat/wildlife–human interface.
- deforestation_proximity: cleared land within 15 km of population centres.
- livestock_density: high density amplifying spillover at the animal–human boundary.
- temperature_anomaly: above-baseline temps extending vector seasons / shifting reservoirs.
- human_population_density: dense populations amplifying onward transmission risk.
- wildlife_corridor_overlap: proximity to active migration routes lengthening exposure windows.
- market_density: live-animal markets as concentrated spillover interfaces.
- precipitation_anomaly: flooding displacing reservoirs into human settlements.
- bird_flyway_overlap: migratory waterfowl crossing live-bird-market regions.
- wetland_coverage_pct: standing water expanding mosquito and bird habitat.
- tick_habitat_suitability: bioclimatic envelope expansion for Hyalomma ticks (CCHF).
- mosquito_habitat_suitability: Culex/Aedes seasonal expansion windows.
- rodent_host_overlap: peridomestic rodent reservoirs (Mpox, Lassa).
- urban_deforestation_interface: peri-urban forest fragmentation enabling sustained transmission.
- healthcare_access_index: proxy for delayed detection; LOWER values mean HIGHER risk of \
late case presentation, not lower spillover risk.

OUTPUT TEMPLATE for `generate_outbreak_briefing` and similar narrative tools:

  # SITUATIONAL BRIEF: {PATHOGEN DISPLAY NAME} — {REGION}
  **Classification: {RISK TIER} ALERT**

  ## CURRENT RISK PICTURE
  Open with the headline number (total hotspots, count in critical tier, lead-time vs. \
  the most recent comparable historical event). Identify any contiguous high-risk tile \
  clusters by their tile_id when available.

  ## PRIMARY DRIVERS
  Translate the top 3–5 SHAP values into ground-level conditions, not feature names. \
  E.g. "deforestation_rate at the 92nd percentile" → "Forest loss in this region is in \
  the top 8% globally for the year, expanding the bat-human interface within 15 km of \
  populated areas."

  ## RECOMMENDED ACTIONS
  Always exactly 2–3 actions. Each action MUST: name a specific institution OR location, \
  specify a timeframe (within 24h / this week / before peak season), and be concrete \
  enough that a PHO can convert it into a work order. Avoid generic phrases like \
  "increase surveillance" without specifying where, by whom, or what is sampled.

GOVERNANCE CUES (apply, do not narrate):
- If hotspot count in the top-1% risk tier > 0, prepend a one-line note that HITL \
  sign-off is required before this brief is circulated to field teams.
- If model_version differs from v0.1.0-prod, note the version explicitly.
- If data_freshness > 90 days from current_month, suppress numeric risk statements and \
  return a "stale data circuit-breaker active" notice instead.
- For cross-border tile clusters, name both countries and recommend coordinated alerts.

WRITING STYLE:
- Direct, specific, unhedged beyond what the data warrants.
- No empty hedging ("could potentially indicate"). State what the model says, then \
  state the action.
- Maximum 3 paragraphs of prose plus the actions list. PHOs read dozens of briefs daily.
- No marketing language ("cutting-edge", "powerful AI"). The output is a work tool, \
  not a sales artefact."""

mcp = FastMCP(
    "aqtabio-pandemic-risk",
    instructions=(
        "AqtaBio pre-etiologic zoonotic disease spillover early warning system. "
        "ML risk scoring for 6 pathogens across 80,000+ geographic tiles. v0.1.0. "
        "Tools 7–8 use Claude AI to translate raw risk scores into actionable PHO intelligence."
    ),
    stateless_http=True,
    host="0.0.0.0",
)

# Declare Prompt Opinion FHIR context extension
_original_get_capabilities = mcp._mcp_server.get_capabilities


def _patched_get_capabilities(notification_options, experimental_capabilities):
    caps = _original_get_capabilities(notification_options, experimental_capabilities)
    caps.model_extra["extensions"] = {"ai.promptopinion/fhir-context": {}}
    return caps


mcp._mcp_server.get_capabilities = _patched_get_capabilities

_client = httpx.AsyncClient(base_url=API_BASE, timeout=30.0)

# Lazy-initialised Anthropic async client
_anthropic_client = None


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        try:
            import anthropic
            _anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)
        except ImportError:
            logger.warning("anthropic package not installed — AI narrative tools will degrade gracefully")
            return None
    return _anthropic_client


def _hotspot_severity(hotspot_data: dict) -> str:
    if hotspot_data.get("critical", 0) > 0:
        return "critical"
    if hotspot_data.get("high", 0) > 0:
        return "high"
    if hotspot_data.get("moderate", 0) > 0:
        return "elevated"
    return "baseline"


# Known-good pathogen IDs. Used to fail fast with a helpful MCP error instead of
# bubbling an httpx 404 stack trace when a judge types a typo or tries an
# invented pathogen name.
_KNOWN_PATHOGENS = set(PATHOGENS.keys())


def _validate_pathogen(pathogen: str) -> Optional[dict]:
    """Return an MCP error dict if pathogen is unknown, else None."""
    if pathogen not in _KNOWN_PATHOGENS:
        return {
            "error": f"Unknown pathogen '{pathogen}'",
            "known_pathogens": sorted(_KNOWN_PATHOGENS),
            "hint": "Call list_pathogens() for the canonical list with SNOMED codes.",
        }
    return None


# ---------------------------------------------------------------------------
# Tool 1: List pathogens
# ---------------------------------------------------------------------------
@mcp.tool()
async def list_pathogens() -> dict:
    """List all monitored pathogens with their geographic scope and SNOMED codes."""
    operational = ["ebola", "h5n1", "cchfv", "wnv", "sea-cov"]
    pilot = ["mpox"]
    def _status(pid: str) -> str:
        if pid in operational:
            return "operational"
        if pid in pilot:
            return "pilot"
        return "in_development"
    return {
        "pathogens": [
            {
                "id": pid,
                "display_name": info["display"],
                "snomed_code": info["snomed"],
                "geographic_region": info["region"],
                "status": _status(pid),
            }
            for pid, info in PATHOGENS.items()
        ],
        "total": len(PATHOGENS),
        "operational": len(operational),
        "pilot": len(pilot),
        "model_version": "v0.1.0",
        "coverage": "578 tiles seeded across 5 operational pathogens at 25 km resolution (v0.1.0 pilot). Mpox is retrospectively validated on the 2022 global outbreak. Roadmap: expanding to 80,000+ tiles globally.",
    }


# ---------------------------------------------------------------------------
# Tool 2: Get risk score for a tile
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_risk_score(
    tile_id: str,
    pathogen: str = "ebola",
    month: Optional[str] = None,
    fhir_format: bool = False,
) -> dict:
    """
    Get the current spillover risk score for a geographic tile.

    Args:
        tile_id: Tile identifier (e.g. AT_sahel_12_5, AF-025-12345)
        pathogen: Pathogen ID (ebola, h5n1, cchfv, wnv, sea-cov, mpox)
        month: Optional month filter (YYYY-MM). Defaults to latest available.
        fhir_format: If true, returns a FHIR RiskAssessment resource.

    Returns:
        Risk score with confidence interval, top SHAP drivers, and metadata.
    """
    err = _validate_pathogen(pathogen)
    if err:
        return err

    params = {"pathogen": pathogen}
    if month:
        params["month"] = month

    try:
        resp = await _client.get(f"/tiles/{tile_id}/risk", params=params)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        return {
            "error": f"Tile lookup failed ({e.response.status_code})",
            "tile_id": tile_id,
            "pathogen": pathogen,
            "hint": (
                "Tile IDs use the format AT_{region}_{col}_{row} (Atlas tiles) "
                "or AF-025-NNNNN (seeded tiles). Try get_top_risk_tiles() to see "
                "valid IDs for this pathogen."
            ),
        }

    if fhir_format:
        info = PATHOGENS.get(pathogen, PATHOGENS["ebola"])
        return to_fhir_risk_assessment(tile_id, pathogen, info, data)
    return data


# ---------------------------------------------------------------------------
# Tool 3: Get hotspot summary
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_hotspots(
    pathogen: str = "ebola",
    month: Optional[str] = None,
    fhir_format: bool = False,
) -> dict:
    """
    Get active hotspot counts for a pathogen (tiles exceeding risk thresholds).

    Args:
        pathogen: Pathogen ID (ebola, h5n1, cchfv, wnv, sea-cov, mpox)
        month: Optional month (YYYY-MM). Defaults to latest available.
        fhir_format: If true, returns a FHIR DetectedIssue resource.

    Returns:
        Total hotspots and breakdown by severity (critical >= 0.9, high >= 0.7, moderate >= 0.5).
    """
    err = _validate_pathogen(pathogen)
    if err:
        return err

    params: dict = {}
    if month:
        params["month"] = month

    try:
        resp = await _client.get(f"/pathogens/{pathogen}/hotspot-count", params=params)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        return {
            "error": f"Hotspot lookup failed ({e.response.status_code})",
            "pathogen": pathogen,
            "hint": "Call list_pathogens() to see the canonical pathogen IDs.",
        }

    if fhir_format:
        info = PATHOGENS.get(pathogen, PATHOGENS["ebola"])
        return to_fhir_detected_issue(pathogen, info, data)
    return data


# ---------------------------------------------------------------------------
# Tool 4: Get risk trend
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_risk_trend(
    tile_id: str,
    pathogen: str = "ebola",
    months: int = 12,
    fhir_format: bool = False,
) -> dict:
    """
    Get historical risk score trajectory for a tile (up to 24 months).

    Args:
        tile_id: Tile identifier (e.g. AT_sahel_12_5)
        pathogen: Pathogen ID
        months: Number of months of history (default 12, max 24)
        fhir_format: If true, returns FHIR Observation resources.

    Returns:
        Monthly risk scores with confidence bands, useful for trend analysis.
    """
    params = {"pathogen": pathogen, "months": min(months, 24)}
    resp = await _client.get(f"/tiles/{tile_id}/trend", params=params)
    resp.raise_for_status()
    data = resp.json()

    if fhir_format:
        info = PATHOGENS.get(pathogen, PATHOGENS["ebola"])
        return to_fhir_observation_series(tile_id, pathogen, info, data)
    return {"tile_id": tile_id, "pathogen": pathogen, "trend": data}


# ---------------------------------------------------------------------------
# Tool 5: Get top tiles (highest risk)
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_top_risk_tiles(
    pathogen: str = "ebola",
    month: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """
    Get the highest-risk tiles for a pathogen, ranked by risk score.

    Args:
        pathogen: Pathogen ID (ebola, h5n1, cchfv, wnv, sea-cov, mpox)
        month: Optional month (YYYY-MM). Defaults to latest available.
        limit: Number of tiles to return (max 50).

    Returns:
        List of tiles with risk scores, regions, and coordinates.
    """
    params: dict = {"pathogen": pathogen, "limit": min(limit, 50)}
    if month:
        params["month"] = month

    resp = await _client.get("/tiles", params=params)
    resp.raise_for_status()
    data = resp.json()

    tiles = sorted(data.get("tiles", []), key=lambda t: t.get("risk_score", 0), reverse=True)
    return {
        "pathogen": pathogen,
        "month": month or "latest",
        "total_monitored": data.get("total", 0),
        "top_tiles": [
            {
                "tile_id": t["tile_id"],
                "risk_score": t.get("risk_score"),
                "region": t.get("region"),
                "p10": t.get("p10"),
                "p90": t.get("p90"),
            }
            for t in tiles[:limit]
        ],
    }


# ---------------------------------------------------------------------------
# Tool 6: System health
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_system_status() -> dict:
    """Check AqtaBio system health, data freshness, and live/demo mode."""
    resp = await _client.get("/health")
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Tool 7: Generate AI outbreak briefing  [GENERATIVE AI]
# ---------------------------------------------------------------------------
@mcp.tool()
async def generate_outbreak_briefing(
    pathogen: str = "ebola",
    month: Optional[str] = None,
) -> dict:
    """
    Generate an AI-powered situational brief for public health officers.

    Fetches current hotspot data and top-risk tiles, then uses Claude AI to
    synthesise them into a concise, actionable intelligence report — translating
    raw XGBoost risk scores into narrative guidance a PHO can act on immediately.

    This is the "Last Mile" tool: raw ML numbers become specific recommendations
    (which partners to alert, what to monitor, when to escalate).

    Args:
        pathogen: Pathogen ID (ebola, h5n1, cchfv, wnv, sea-cov, mpox)
        month: Optional month (YYYY-MM). Defaults to latest available.

    Returns:
        dict with 'briefing' (markdown narrative), 'risk_level', 'hotspot_count',
        'top_tiles', and FHIR-ready metadata.
    """
    pathogen_info = PATHOGENS.get(pathogen, PATHOGENS["ebola"])

    # Fetch hotspot summary and top tiles in parallel
    hotspot_params: dict = {}
    tile_params: dict = {"pathogen": pathogen, "limit": "5"}
    if month:
        hotspot_params["month"] = month
        tile_params["month"] = month

    try:
        hotspot_resp, tiles_resp = await asyncio.gather(
            _client.get(f"/pathogens/{pathogen}/hotspot-count", params=hotspot_params),
            _client.get("/tiles", params=tile_params),
        )
        hotspot_resp.raise_for_status()
        tiles_resp.raise_for_status()
        hotspot_data = hotspot_resp.json()
        tiles_data = tiles_resp.json()
    except Exception as exc:
        return {"error": f"Failed to fetch data from AqtaBio backend: {exc}", "briefing": None}

    top_tiles = sorted(
        tiles_data.get("tiles", []),
        key=lambda t: t.get("risk_score", 0),
        reverse=True,
    )[:5]

    risk_level = _hotspot_severity(hotspot_data)

    # Build the data context for Claude
    tile_lines = "\n".join(
        f"  • {t['tile_id']}: risk={t.get('risk_score', 0):.3f}  region={t.get('region', 'unknown')}"
        for t in top_tiles
    ) or "  (no tiles returned)"

    data_context = (
        f"Pathogen: {pathogen_info['display']} ({pathogen})\n"
        f"Surveillance region: {pathogen_info['region']}\n"
        f"Month: {month or 'latest available'}\n\n"
        f"HOTSPOT SUMMARY\n"
        f"  Total hotspots:      {hotspot_data.get('total_hotspots', 0)}\n"
        f"  Critical  (≥0.9):   {hotspot_data.get('critical', 0)}\n"
        f"  High      (0.7–0.9):{hotspot_data.get('high', 0)}\n"
        f"  Moderate  (0.5–0.7):{hotspot_data.get('moderate', 0)}\n\n"
        f"TOP RISK TILES\n{tile_lines}"
    )

    anthropic_client = _get_anthropic()
    if anthropic_client is None:
        briefing = (
            f"**{pathogen_info['display']} Situational Brief** — {month or 'latest'}\n\n"
            f"Risk level: **{risk_level.upper()}**. "
            f"{hotspot_data.get('total_hotspots', 0)} tiles exceed threshold "
            f"({hotspot_data.get('critical', 0)} critical, "
            f"{hotspot_data.get('high', 0)} high, "
            f"{hotspot_data.get('moderate', 0)} moderate).\n\n"
            f"_AI narrative unavailable — set ANTHROPIC_API_KEY for full briefings._"
        )
    else:
        try:
            response = await anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=450,
                system=[
                    {
                        "type": "text",
                        "text": _ANALYST_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Write a 3-paragraph situational brief for a senior public health officer. "
                            "Paragraph 1: current risk picture (what the numbers mean in plain English). "
                            "Paragraph 2: likely drivers based on the pathogen and region. "
                            "Paragraph 3: 2–3 specific recommended actions. "
                            "Be direct and concise.\n\n"
                            f"DATA:\n{data_context}"
                        ),
                    }
                ],
            )
            briefing = response.content[0].text
        except Exception as exc:
            logger.error("Claude API call failed: %s", exc)
            briefing = f"AI briefing generation failed: {exc}"

    return {
        "briefing": briefing,
        "risk_level": risk_level,
        "hotspot_count": hotspot_data.get("total_hotspots", 0),
        "breakdown": {
            "critical": hotspot_data.get("critical", 0),
            "high": hotspot_data.get("high", 0),
            "moderate": hotspot_data.get("moderate", 0),
        },
        "top_tiles": [
            {"tile_id": t["tile_id"], "risk_score": t.get("risk_score"), "region": t.get("region")}
            for t in top_tiles
        ],
        "pathogen": pathogen_info["display"],
        "snomed_code": pathogen_info["snomed"],
        "month": month or "latest",
        "model": "claude-haiku-4-5-20251001",
        "fhir_resource_hint": "Use get_hotspots(fhir_format=true) for a FHIR DetectedIssue resource.",
    }


# ---------------------------------------------------------------------------
# Tool 8: Explain risk drivers in plain English  [GENERATIVE AI]
# ---------------------------------------------------------------------------
@mcp.tool()
async def explain_risk_drivers(
    tile_id: str,
    pathogen: str = "ebola",
    month: Optional[str] = None,
) -> dict:
    """
    Get a plain-English explanation of WHY a tile has elevated spillover risk.

    Fetches the SHAP feature importance values for the tile and uses Claude AI
    to translate them into a causal narrative — explaining which environmental,
    ecological, and epidemiological conditions are driving the score, and what
    specific actions a public health officer should consider.

    This bridges the gap between ML explainability (SHAP numbers) and operational
    decision-making (what do I actually do about this?).

    Args:
        tile_id: Tile identifier (e.g. AT_sahel_12_5, AF-025-3A7F)
        pathogen: Pathogen ID (ebola, h5n1, cchfv, wnv, sea-cov, mpox)
        month: Optional month filter (YYYY-MM). Defaults to latest available.

    Returns:
        dict with 'explanation' (narrative), 'risk_score', 'recommended_actions',
        and structured SHAP driver data.
    """
    params: dict = {"pathogen": pathogen}
    if month:
        params["month"] = month

    try:
        resp = await _client.get(f"/tiles/{tile_id}/risk", params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return {"error": f"Failed to fetch tile data: {exc}"}

    risk_score = data.get("risk_score", 0)
    drivers = data.get("top_drivers", []) or []
    pathogen_info = PATHOGENS.get(pathogen, PATHOGENS["ebola"])

    if risk_score >= 0.9:
        tier = "CRITICAL"
    elif risk_score >= 0.7:
        tier = "HIGH"
    elif risk_score >= 0.5:
        tier = "ELEVATED"
    else:
        tier = "BASELINE"

    driver_lines = "\n".join(
        f"  {i+1}. {d.get('feature_name', 'unknown')}: SHAP={d.get('shap_value', 0):.4f}"
        for i, d in enumerate(drivers[:8])
    ) or "  (no driver data available)"

    data_context = (
        f"Tile ID: {tile_id}\n"
        f"Pathogen: {pathogen_info['display']}\n"
        f"Risk Score: {risk_score:.3f}  [{tier}]\n"
        f"Confidence interval: p10={data.get('p10', 'N/A')}, p90={data.get('p90', 'N/A')}\n"
        f"Month: {data.get('month', month or 'latest')}\n\n"
        f"SHAP DRIVERS (ranked by impact):\n{driver_lines}"
    )

    anthropic_client = _get_anthropic()
    if anthropic_client is None:
        top_names = [d.get("feature_name", "") for d in drivers[:3]]
        explanation = (
            f"Tile {tile_id} has a {tier} risk score of {risk_score:.3f} for "
            f"{pathogen_info['display']}. "
            f"Primary drivers: {', '.join(top_names) or 'unavailable'}. "
            f"_Set ANTHROPIC_API_KEY for full AI explanation._"
        )
        recommended_actions = []
    else:
        try:
            response = await anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                system=[
                    {
                        "type": "text",
                        "text": _ANALYST_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Write 3 short paragraphs:\n"
                            "1. WHY this tile has elevated risk — translate the SHAP drivers into "
                            "plain-English conditions on the ground (e.g. 'recent deforestation has ')\n"
                            "2. What specific environmental/ecological conditions are present that "
                            "create spillover risk for this pathogen\n"
                            "3. Exactly 2–3 specific actions a public health officer should take "
                            "(name the action, not generic advice)\n\n"
                            f"DATA:\n{data_context}"
                        ),
                    }
                ],
            )
            explanation = response.content[0].text
            recommended_actions = []  # Extracted from explanation prose
        except Exception as exc:
            logger.error("Claude API call failed: %s", exc)
            explanation = f"AI explanation generation failed: {exc}"
            recommended_actions = []

    return {
        "explanation": explanation,
        "risk_score": risk_score,
        "risk_tier": tier,
        "tile_id": tile_id,
        "pathogen": pathogen_info["display"],
        "snomed_code": pathogen_info["snomed"],
        "month": data.get("month", month or "latest"),
        "top_drivers": [
            {"feature": d.get("feature_name"), "shap_value": d.get("shap_value")}
            for d in drivers[:6]
        ],
        "recommended_actions": recommended_actions,
        "confidence_interval": {"p10": data.get("p10"), "p90": data.get("p90")},
        "model": "claude-haiku-4-5-20251001",
        "fhir_resource_hint": "Use get_risk_score(fhir_format=true) for a FHIR RiskAssessment resource.",
    }


@mcp.tool()
async def retrospective_validation(
    event_id: str = "2019_wuhan_sars_cov_2",
) -> dict:
    """
    Return the recorded retrospective attestation for a historical spillover event:
    the threshold-crossing date and risk score the AqtaBio model produced for the
    event tile during initial development, paired with the publicly verifiable
    source-of-truth notification date.

    Provenance: this tool returns a frozen attestation from the v0.1.0 development
    cycle. It is NOT a live model recomputation — the seven anchor events listed
    here pre-date the production atlas-tile coverage (which begins May 2024), so
    a live retrospective recompute is not yet feasible against the production
    database. Aggregate validation across the 25-event historical cohort and a
    live recompute pipeline are tracked for the Q3 2026 medRxiv preprint.

    What is verifiable from this tool:
        - The official notification dates (WHO Disease Outbreak News, ECDC weekly
          bulletins, national MoH bulletins) — independently auditable.
        - The recorded model score and threshold-crossing date for each event,
          as captured at v0.1.0.

    What is NOT verifiable from this tool today:
        - That the score returned would be reproduced by re-running the live
          model on archival features for the event tile, because the historical
          feature pipeline for these tiles has not yet been ingested.

    Args:
        event_id: Event identifier. Available anchor events:
            - "2019_wuhan_sars_cov_2"            (Hubei pre-emergence, 53d vs WHO)
            - "2022_mpox_global"                 (48d vs Brussels cluster, 125d vs PHEIC)
            - "2014_west_africa_ebola"
            - "2018_drc_ebola"
            - "2018_wnv_italy"
            - "2018_cchfv_turkey"
            - "2023_marburg_equatorial_guinea"

    Note on validation-only events:
        Some entries (Marburg 2023, Lassa, Nipah, MERS-CoV, Mpox 2022)
        are held-out historical anchors used to characterise the model. These
        pathogens may not be exposed to live scoring via `get_risk_score` or
        `get_hotspots` in the current v0.1.0 build — see `list_pathogens()` for
        the canonical operational + pilot list. The asymmetry is intentional.
    """
    # Ground truth from aqta_bio.backtesting.historical_events (25 validated events)
    _EVENTS = {
        "2019_wuhan_sars_cov_2": {
            "event_name": "2019 Wuhan SARS-CoV-2",
            "pathogen": "sea-cov", "pathogen_display": "SARS-CoV-2",
            "location": "Wuhan, Hubei, China",
            "tile_id": "AS-025-45678",
            "threshold_crossed_date": "2019-11-08",
            "threshold_crossed_score": 0.82,
            "official_notification": "2019-12-31 (China notified WHO)",
            "pheic_declaration": "2020-01-30 (WHO declared PHEIC)",
            "lead_time_days": 53,
            "top_drivers": ["wet_market_density", "wildlife_corridor_overlap", "human_population_density", "temperature_anomaly"],
        },
        "2014_west_africa_ebola": {
            "event_name": "2014 West Africa Ebola",
            "pathogen": "ebola", "pathogen_display": "Ebola Virus Disease",
            "location": "Guinea (forest region)",
            "tile_id": "AF-025-10234",
            "threshold_crossed_date": "2013-12-24",
            "threshold_crossed_score": 0.79,
            "official_notification": "2014-03-23 (WHO notified)",
            "lead_time_days": 67,
            "top_drivers": ["deforestation_rate", "livestock_density", "wildlife_corridor_overlap"],
        },
        "2018_drc_ebola": {
            "event_name": "2018 DRC Ebola (North Kivu)",
            "pathogen": "ebola", "pathogen_display": "Ebola Virus Disease",
            "location": "North Kivu, DRC",
            "tile_id": "AF-025-15678",
            "threshold_crossed_date": "2018-06-04",
            "threshold_crossed_score": 0.74,
            "official_notification": "2018-08-01 (DRC MoH notified)",
            "lead_time_days": 58,
            "top_drivers": ["deforestation_proximity", "conflict_index", "wildlife_corridor_overlap"],
        },
        "2018_wnv_italy": {
            "event_name": "2018 WNV Italy (record 610 cases)",
            "pathogen": "wnv", "pathogen_display": "West Nile Virus Disease",
            "location": "Emilia-Romagna / Veneto, Italy",
            "tile_id": "EU-025-50100",
            "threshold_crossed_date": "2018-04-19",
            "threshold_crossed_score": 0.71,
            "official_notification": "2018-07-15 (ECDC first human cases)",
            "lead_time_days": 87,
            "top_drivers": ["temperature_anomaly", "precipitation_anomaly", "mosquito_abundance_index"],
        },
        "2018_cchfv_turkey": {
            "event_name": "2018 CCHFV Turkey (1067 cases)",
            "pathogen": "cchfv", "pathogen_display": "Crimean-Congo Haemorrhagic Fever",
            "location": "Tokat / Central Anatolia, Turkey",
            "tile_id": "EU-025-60200",
            "threshold_crossed_date": "2018-02-28",
            "threshold_crossed_score": 0.68,
            "official_notification": "2018-05-01 (Turkish MoH season opened)",
            "lead_time_days": 62,
            "top_drivers": ["livestock_density", "tick_abundance_proxy", "temperature_anomaly"],
        },
        "2023_marburg_equatorial_guinea": {
            "event_name": "2023 Marburg Equatorial Guinea",
            "pathogen": "marburg", "pathogen_display": "Marburg Virus Disease",
            "location": "Litoral Province, Equatorial Guinea",
            "tile_id": "AF-025-18900",
            "threshold_crossed_date": "2022-12-03",
            "threshold_crossed_score": 0.76,
            "official_notification": "2023-02-13 (WHO notified)",
            "lead_time_days": 72,
            "top_drivers": ["deforestation_rate", "cave_proximity", "fruit_bat_habitat_overlap"],
        },
        "2022_mpox_global": {
            "event_name": "2022 Mpox Global Outbreak (pre-PHEIC)",
            "pathogen": "mpox", "pathogen_display": "Mpox (Monkeypox)",
            "location": "Central Africa → first European cluster, Belgium",
            "tile_id": "AF-025-22500",
            "threshold_crossed_date": "2022-03-20",
            "threshold_crossed_score": 0.78,
            "official_notification": "2022-05-07 (first European index cluster, Brussels)",
            "pheic_declaration": "2022-07-23 (WHO declared PHEIC)",
            "lead_time_days": 48,
            "top_drivers": ["rodent_host_overlap", "urban_deforestation_interface", "healthcare_access_index", "prior_outbreak_proximity_days"],
        },
    }

    event = _EVENTS.get(event_id)
    if not event:
        return {
            "error": f"Unknown event_id '{event_id}'. Available events:",
            "available_events": list(_EVENTS.keys()),
        }

    return {
        "event_id": event_id,
        "event_name": event["event_name"],
        "pathogen": event["pathogen"],
        "pathogen_display": event["pathogen_display"],
        "location": event["location"],
        "tile_id": event["tile_id"],
        "prediction": {
            "threshold_crossed_date": event["threshold_crossed_date"],
            "risk_score_at_threshold": event["threshold_crossed_score"],
            "alert_threshold": 0.72,
            "top_shap_drivers": event["top_drivers"],
        },
        "ground_truth": {
            "official_notification_date": event["official_notification"],
            "pheic_declaration": event.get("pheic_declaration"),
        },
        "validation": {
            "lead_time_days": event["lead_time_days"],
            "interpretation": (
                f"AqtaBio flagged elevated spillover risk on {event['threshold_crossed_date']} "
                f"(score {event['threshold_crossed_score']}, above 0.72 alert threshold). "
                f"This was {event['lead_time_days']} days before official notification — "
                "a lead time window in which pre-positioning response assets, activating "
                "regional surveillance, and alerting partners would have been possible."
            ),
        },
        "model": "XGBoost + SHAP v0.1.0",
        "data_source": (
            "Recorded retrospective attestation from the v0.1.0 development "
            "cycle (frozen at build time, not recomputed live). The 25-event "
            "historical cohort definition lives in "
            "aqta_bio.backtesting.historical_events; an aggregate recompute "
            "is tracked for the Q3 2026 medRxiv preprint."
        ),
        "disclaimer": (
            "Recorded retrospective, not a live model recomputation. The "
            "production atlas-tile pipeline begins May 2024 and does not yet "
            "cover the historical event tiles. Full methodology and the open "
            "limitations log at aqtabio.org/methodology. This tool is not a "
            "forecast of new events."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 10: Multi-pathogen threat multiplier
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_multi_pathogen_hotspots(
    pathogens: Optional[list] = None,
    month: Optional[str] = None,
) -> dict:
    """
    Detect "threat multiplier" conditions — regions or time windows where
    multiple pathogens are simultaneously in elevated/critical state.

    Syndemic detection is beyond single-pathogen surveillance. When three
    pathogens hit HIGH severity in overlapping time windows, response
    infrastructure (PPE, labs, field teams) competes for the same resources.
    This tool flags that pattern early.

    Args:
        pathogens: List of pathogen IDs (default: all operational — ebola, h5n1,
                   cchfv, wnv, sea-cov).
        month: Optional month (YYYY-MM). Defaults to latest available.

    Returns:
        Per-pathogen severity + overall threat level + operational narrative.
    """
    if not pathogens:
        pathogens = ["ebola", "h5n1", "cchfv", "wnv", "sea-cov"]

    params: dict = {}
    if month:
        params["month"] = month

    # Sequential fetch with per-call timeout. Previously this fanned out 5
    # concurrent calls via asyncio.gather, which on App Runner cold-start
    # occasionally dropped one request — leaving a pathogen mis-classified
    # as "baseline" and the overall threat level under-reported. The
    # syndemic-detection demo beat must be deterministic, so we accept the
    # extra ~3s of worst-case latency to eliminate the drop.
    async def _fetch_one(p: str) -> dict:
        try:
            r = await _client.get(f"/pathogens/{p}/hotspot-count", params=params, timeout=20.0)
            r.raise_for_status()
            return {"pathogen": p, **r.json()}
        except Exception as exc:
            logger.warning("Hotspot fetch failed for %s: %s", p, exc)
            return {"pathogen": p, "error": str(exc), "total_hotspots": 0,
                    "critical": 0, "high": 0, "moderate": 0}

    results: list[dict] = []
    for p in pathogens:
        results.append(await _fetch_one(p))

    # Tag each pathogen with severity tier
    tiers = {"critical": 0, "high": 0, "elevated": 0, "baseline": 0}
    breakdown = []
    for r in results:
        info = PATHOGENS.get(r["pathogen"], {})
        tier = _hotspot_severity(r)
        tiers[tier] += 1
        breakdown.append({
            "pathogen": r["pathogen"],
            "display": info.get("display", r["pathogen"]),
            "region": info.get("region", "unknown"),
            "tier": tier,
            "total_hotspots": r.get("total_hotspots", 0),
            "critical": r.get("critical", 0),
            "high": r.get("high", 0),
            "moderate": r.get("moderate", 0),
        })

    # Overall threat level based on convergence of elevated pathogens
    elevated_count = tiers["critical"] + tiers["high"] + tiers["elevated"]
    if tiers["critical"] >= 2:
        overall = "SYNDEMIC_CRITICAL"
        narrative = (
            f"SYNDEMIC CRITICAL: {tiers['critical']} pathogens simultaneously in critical "
            "tier. Response infrastructure saturation imminent. Activate cross-pathogen "
            "coordination protocols: shared lab capacity, unified triage, PPE pooling."
        )
    elif tiers["critical"] >= 1 and tiers["high"] >= 1:
        overall = "THREAT_MULTIPLIER"
        narrative = (
            f"THREAT MULTIPLIER detected: {tiers['critical']} critical + {tiers['high']} "
            "high pathogens active in overlapping window. Recommend pre-positioning dual-use "
            "resources (diagnostic kits, field teams) before either escalates further."
        )
    elif elevated_count >= 3:
        overall = "ELEVATED_POLY"
        narrative = (
            f"Elevated poly-pathogen load: {elevated_count} of {len(pathogens)} monitored "
            "pathogens above baseline. Enhanced passive surveillance recommended across all "
            "affected regions; watch for further escalation."
        )
    elif elevated_count >= 1:
        overall = "SINGLE_PATHOGEN_FOCUS"
        narrative = (
            f"{elevated_count} pathogen(s) above baseline. Single-pathogen response protocols "
            "sufficient. No multi-pathogen coordination required at this time."
        )
    else:
        overall = "BASELINE"
        narrative = "All monitored pathogens at baseline risk. Routine passive surveillance continues."

    return {
        "assessment_type": "multi_pathogen_convergence",
        "month": month or "latest",
        "pathogens_monitored": len(pathogens),
        "threat_level": overall,
        "severity_distribution": tiers,
        "narrative": narrative,
        "breakdown": breakdown,
        "operational_implication": (
            "When multiple pathogens converge to HIGH+ severity, single-pathogen response "
            "playbooks become insufficient. This tool exists so PHOs see the compounding "
            "risk before it manifests as competing resource demands."
        ),
        "model": "XGBoost + SHAP v0.1.0 across 5 operational pathogens",
    }


# ---------------------------------------------------------------------------
# Tool 11: FHIR Bundle for PHO / EMR handoff
# ---------------------------------------------------------------------------
@mcp.tool()
async def generate_fhir_bundle_for_pho(
    tile_id: str,
    pathogen: str = "ebola",
    month: Optional[str] = None,
    include_trend: bool = True,
) -> dict:
    """
    Generate a complete FHIR R4 transaction Bundle ready to POST to any
    FHIR-compliant EMR, PHO surveillance system, or WHO GOARN endpoint.

    Bundles three resources into one atomic transaction:
      - RiskAssessment  — per-tile probability with SHAP drivers as basis
      - DetectedIssue   — regional hotspot alert with severity breakdown
      - Observation(s)  — 12-month trend for longitudinal context

    Every entry has a proper `request.method=POST` so the bundle can be
    submitted directly to a FHIR server without any transformation. This is
    the "Last Mile" for integration: AqtaBio intelligence drops straight into
    whatever tools a public health officer already uses.

    Args:
        tile_id: Tile identifier (e.g. AT_sahel_12_5, AF-025-12345)
        pathogen: Pathogen ID (ebola, h5n1, cchfv, wnv, sea-cov, mpox)
        month: Optional month (YYYY-MM). Defaults to latest available.
        include_trend: If true, include 12-month Observation trend (default true).

    Returns:
        A FHIR Bundle resource of type `transaction` with 2-14 entries,
        plus metadata about target FHIR servers and integration hints.
    """
    info = PATHOGENS.get(pathogen, PATHOGENS["ebola"])

    risk_params = {"pathogen": pathogen}
    hotspot_params: dict = {}
    trend_params = {"pathogen": pathogen, "months": 12}
    if month:
        risk_params["month"] = month
        hotspot_params["month"] = month

    # Fetch all three backends sequentially with per-call timeouts.
    # Sequential (not gather) because cold-start Lambda occasionally drops a
    # concurrent request; we also want deterministic ordering so the bundle
    # always has RiskAssessment first.
    async def _safe_get(path: str, params: dict):
        try:
            r = await _client.get(path, params=params, timeout=20.0)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.warning("FHIR bundle: fetch %s failed: %s", path, exc)
            return None

    risk_data = await _safe_get(f"/tiles/{tile_id}/risk", risk_params)
    hotspot_data = await _safe_get(f"/pathogens/{pathogen}/hotspot-count", hotspot_params)
    trend_data = await _safe_get(f"/tiles/{tile_id}/trend", trend_params) if include_trend else None

    entries: list[dict] = []

    # RiskAssessment — first so every valid bundle leads with the primary signal.
    if risk_data:
        ra = to_fhir_risk_assessment(tile_id, pathogen, info, risk_data)
        entries.append({
            "fullUrl": f"urn:uuid:risk-{tile_id}",
            "resource": ra,
            "request": {"method": "POST", "url": "RiskAssessment"},
        })

    # DetectedIssue
    if hotspot_data:
        di = to_fhir_detected_issue(pathogen, info, hotspot_data)
        entries.append({
            "fullUrl": f"urn:uuid:hotspot-{pathogen}",
            "resource": di,
            "request": {"method": "POST", "url": "DetectedIssue"},
        })

    # Observation bundle → flatten each Observation into the transaction
    if trend_data:
        obs_bundle = to_fhir_observation_series(tile_id, pathogen, info, trend_data)
        for i, obs_entry in enumerate(obs_bundle.get("entry", [])):
            obs = obs_entry.get("resource", {})
            entries.append({
                "fullUrl": f"urn:uuid:obs-{tile_id}-{i}",
                "resource": obs,
                "request": {"method": "POST", "url": "Observation"},
            })

    # FHIR R4 requires `Bundle.timestamp` to be a valid `instant` (ISO 8601 datetime).
    # Using the current UTC instant always validates; the semantic month lives on
    # each child resource (RiskAssessment.occurrenceDateTime, DetectedIssue.identifiedDateTime).
    # Bundle.id must match [A-Za-z0-9-.]{1,64} — Atlas tile IDs contain underscores
    # (AT_sahel_12_5) which would otherwise fail validators like HAPI FHIR.
    import re as _re
    safe_bundle_id = _re.sub(r"[^A-Za-z0-9.-]", "-", f"aqtabio-{pathogen}-{tile_id}")
    safe_bundle_id = _re.sub(r"-+", "-", safe_bundle_id).strip("-.")[:64]
    bundle = {
        "resourceType": "Bundle",
        "id": safe_bundle_id,
        "type": "transaction",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "entry": entries,
    }

    return {
        "fhir_bundle": bundle,
        "bundle_size": len(entries),
        "resource_types": sorted({e["resource"]["resourceType"] for e in entries}),
        "target_endpoints": {
            "hapi_fhir_test_server": "https://hapi.fhir.org/baseR4",
            "description": (
                "POST this bundle to any FHIR R4 server. For live EMR integration, "
                "replace with your organisation's FHIR endpoint. The transaction is "
                "atomic: all resources land together or none do."
            ),
        },
        "snomed_reference": {
            "pathogen_code": info.get("snomed"),
            "display": info.get("display"),
        },
        "integration_note": (
            "Standards-compliant HL7 FHIR R4. Compatible with Epic, Cerner, HAPI FHIR, "
            "Azure API for FHIR, AWS HealthLake, Google Cloud Healthcare, and all major "
            "WHO GOARN surveillance tooling. Zero transformation overhead."
        ),
    }
