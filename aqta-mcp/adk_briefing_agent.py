"""
ADK + Gemini briefing agent for AqtaBio's MCP backend.

A reference agent that composes AqtaBio's MCP tool surface into a
sentinel-placement recommendation flow for public health agencies
(Africa CDC, ECDC, USAID, IHR-SEA, GAVI, WHO GOARN).

The agent is the wrapper: AqtaBio is the backend. The agent contributes
the orchestration, the Gemini reasoning, and the output shape an
agency can hand to a director for sign-off. The MCP server is
untouched, so the same backend serves Claude Desktop, MCP-aware
clinician workspaces, and any other MCP client without modification.

Run:
    pip install google-genai httpx
    export GOOGLE_API_KEY=<your-key>
    python adk_briefing_agent.py \
        "I am Africa CDC. We have budget for 10 sentinel sites this
         quarter, prioritising H5N1 and Ebola. Where should we place them?"

Environment:
    GOOGLE_API_KEY           Gemini API key
    AQTA_MCP_URL             defaults to the public AppRunner endpoint
    GEMINI_MODEL             defaults to gemini-2.5-flash
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any

# google-adk imports. ADK wraps Gemini's tool-calling loop and gives us
# a stable interface for declarative agents.
try:
    from google.adk.agents import Agent  # type: ignore[import-untyped]
    from google.adk.tools.mcp_tool import McpToolset  # type: ignore[import-untyped]
except ImportError:
    # ADK is not yet a stable PyPI dist at the time of writing; fall back
    # to google-genai + manual MCP client so the file still runs against
    # the public endpoint. The ADK path is the production target;
    # the genai path is the fallback for local development before ADK
    # publishes a stable wheel.
    Agent = None
    McpToolset = None

import google.genai as genai  # type: ignore[import-untyped]
from google.genai import types  # type: ignore[import-untyped]

logger = logging.getLogger("aqta.adk_agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


AQTA_MCP_URL = os.environ.get(
    "AQTA_MCP_URL",
    "https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp",
)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")


SYSTEM_PROMPT = """\
You are AqtaBio's sentinel-placement recommender for public health
agencies operating under a finite surveillance budget.

Your buyer is Africa CDC, ECDC, USAID, IHR-SEA, GAVI, or WHO GOARN —
agencies that decide every quarter where to deploy new sample-collection
sites with limited resources. Your job is to take a region + pathogen +
budget question and answer it by chaining AqtaBio MCP tools.

Default flow (use this unless the user explicitly asks otherwise):

1. Call optimise_sentinel_placement with the user's region, pathogens,
   any existing_sentinels they cite, and budget_sites = the number of
   new sites the agency can afford.
2. For the top-3 selected tiles, call get_risk_score with fhir_format=true
   so each recommendation carries a FHIR RiskAssessment a regulator can
   ingest.
3. Optionally call submit_to_hapi_fhir on the top recommendation so the
   final briefing carries a verifiable third-party FHIR resource URL.
4. If the user is comparing to a historical event (COVID, Mpox, Marburg),
   call retrospective_validation for the relevant anchor.
5. Synthesise a deployment briefing in markdown with: region, pathogens,
   budget, top-N sites with EIG score + rationale, aggregate uncertainty
   reduction estimate, top three SHAP drivers across the picked tiles,
   the explicit method statement from the tool response, and one explicit
   limitation. End with a HAPI URL or FHIR resource id on its own line.

Honesty rules — enforce these regardless of how the user phrases it:
- AqtaBio does NOT predict the next pandemic. It ranks tiles where new
  sentinel sites would most reduce model uncertainty about emergence.
  If the user asks for a "prediction", reframe in your answer.
- Risk scores are population-level pre-etiologic estimates over a
  25 km tile, not per-patient diagnoses.
- The EIG score is a tractable proxy (the formula is in the tool
  response). State this if a user asks how the ranking is computed.
- The 53-day Wuhan attestation, if cited, is a recorded
  development-cycle backtest, not a live 2019 prediction.
- Pathogens whose production tiles are not yet seeded are excluded
  automatically and reported in pathogens_with_data; do not fabricate
  recommendations for them.

Output format: markdown. Five sections max:
  ## Deployment plan (N sites, budget €X)
  ## Top sites
  ## Aggregate uncertainty reduction
  ## Method + limitations
  ## Verification

End with the HAPI URL or a FHIR resource id on its own line so a
reviewer can curl it.
"""


@dataclass
class BriefingResult:
    """Structured return of one end-to-end briefing call."""
    prompt: str
    answer: str
    tools_called: list[str]
    hapi_url: str | None
    fhir_resource_id: str | None
    latency_ms: int


async def run_via_adk(prompt: str) -> BriefingResult:
    """Production path: Google ADK + Gemini + MCP toolset.

    Runs only when google-adk is importable AND ADK exposes the MCP
    toolset adapter. Currently behind a feature flag because ADK is
    pre-1.0 at the time of writing.
    """
    if Agent is None or McpToolset is None:
        raise RuntimeError("google-adk not available; use run_via_genai_fallback")

    toolset = McpToolset.from_streamable_http(url=AQTA_MCP_URL)
    agent = Agent(
        model=GEMINI_MODEL,
        name="aqta_briefing",
        instruction=SYSTEM_PROMPT,
        tools=toolset.tools,
    )
    response = await agent.run(prompt)
    return BriefingResult(
        prompt=prompt,
        answer=response.text,
        tools_called=[c.name for c in response.tool_calls],
        hapi_url=_extract_hapi_url(response.text),
        fhir_resource_id=_extract_fhir_id(response.text),
        latency_ms=int(response.latency_ms),
    )


async def run_via_genai_fallback(prompt: str) -> BriefingResult:
    """Development path: google-genai + a manual streamable-HTTP MCP client.

    Used when google-adk is not installed. Same end-to-end behaviour;
    the agent reasons via Gemini, calls AqtaBio MCP tools, and returns
    a markdown briefing. Slower than the ADK path because the MCP
    client is async-naive.
    """
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")

    client = genai.Client(api_key=GOOGLE_API_KEY)

    # Minimal MCP client over streamable HTTP. Real production would
    # use the ``mcp`` package; this is inlined to keep the example a
    # single self-contained artefact.
    import time
    import httpx
    start = time.monotonic()

    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as http:
        # Discover tools from the MCP server
        tools_resp = await http.post(
            AQTA_MCP_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Accept": "application/json, text/event-stream"},
        )
        tools_resp.raise_for_status()
        tools_data = _parse_sse_or_json(tools_resp.text)
        mcp_tools = tools_data["result"]["tools"]

        # Wrap each MCP tool as a Gemini function declaration
        gemini_tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=t["name"],
                        description=(t.get("description") or "").strip()[:1024],
                        parameters=_clean_schema(t.get("inputSchema", {})),
                    )
                ]
            )
            for t in mcp_tools
        ]

        chat = client.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=gemini_tools,
            ),
        )

        tools_called: list[str] = []
        hapi_url: str | None = None
        fhir_resource_id: str | None = None
        message: Any = prompt

        # Bounded tool-calling loop. Aborts after 8 rounds even if the
        # agent keeps requesting tools, to keep latency predictable.
        # Handles parallel tool-calling: Gemini may return multiple
        # function_call parts in a single response. We iterate every
        # part, batch the function-responses, and send them back as
        # one message so the chat history stays coherent.
        for _ in range(8):
            response = await asyncio.to_thread(chat.send_message, message)
            candidate = response.candidates[0]
            parts = list(candidate.content.parts or [])

            function_calls = [
                p.function_call
                for p in parts
                if getattr(p, "function_call", None)
            ]

            if function_calls:
                response_parts: list = []
                for fc in function_calls:
                    tools_called.append(fc.name)
                    args = dict(fc.args or {})
                    tool_payload = {
                        "jsonrpc": "2.0",
                        "id": len(tools_called) + 1,
                        "method": "tools/call",
                        "params": {"name": fc.name, "arguments": args},
                    }
                    tool_resp = await http.post(
                        AQTA_MCP_URL,
                        json=tool_payload,
                        headers={"Accept": "application/json, text/event-stream"},
                    )
                    tool_resp.raise_for_status()
                    tool_result = _parse_sse_or_json(tool_resp.text)["result"]

                    content_text = _extract_text(tool_result)
                    if fc.name == "submit_to_hapi_fhir" and content_text:
                        try:
                            payload = json.loads(content_text)
                            hapi_url = payload.get("risk_assessment_url")
                            fhir_resource_id = payload.get("resource_id")
                        except json.JSONDecodeError:
                            pass

                    response_parts.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": content_text},
                        )
                    )

                message = response_parts
            else:
                text_chunks = [
                    p.text
                    for p in parts
                    if getattr(p, "text", None)
                ]
                if text_chunks:
                    answer = "\n".join(text_chunks)
                else:
                    answer = (
                        "(agent finished but Gemini returned no text part; "
                        "raw parts: " + repr(parts)[:300] + ")"
                    )
                latency_ms = int((time.monotonic() - start) * 1000)
                return BriefingResult(
                    prompt=prompt,
                    answer=answer,
                    tools_called=tools_called,
                    hapi_url=hapi_url,
                    fhir_resource_id=fhir_resource_id,
                    latency_ms=latency_ms,
                )

        latency_ms = int((time.monotonic() - start) * 1000)
        return BriefingResult(
            prompt=prompt,
            answer="(agent exceeded 8 tool rounds without producing a final answer)",
            tools_called=tools_called,
            hapi_url=hapi_url,
            fhir_resource_id=fhir_resource_id,
            latency_ms=latency_ms,
        )


def _parse_sse_or_json(body: str) -> dict[str, Any]:
    """The MCP server returns Server-Sent Events for streamable HTTP.
    Each event is `event: message\\ndata: {...}`. We accept both pure
    JSON and SSE so the same client works against future transport changes.
    """
    body = body.strip()
    if body.startswith("{"):
        return json.loads(body)
    for line in body.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: "):])
    raise ValueError(f"Unrecognised MCP response: {body[:200]}")


def _extract_text(tool_result: dict[str, Any]) -> str:
    """MCP tool responses wrap content in [{type: 'text', text: '...'}].
    Pull the first text payload out for downstream parsing.
    """
    content = tool_result.get("content") or []
    for entry in content:
        if entry.get("type") == "text":
            return entry.get("text", "")
    return ""


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Gemini's function-declaration schema is JSON-Schema-flavoured but
    rejects fields like ``additionalProperties`` and ``$schema``. Strip them.
    """
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}
    clean: dict[str, Any] = {}
    for k, v in schema.items():
        if k in ("title", "additionalProperties", "$schema", "definitions"):
            continue
        if isinstance(v, dict):
            clean[k] = _clean_schema(v)
        elif isinstance(v, list):
            clean[k] = [_clean_schema(item) if isinstance(item, dict) else item for item in v]
        else:
            clean[k] = v
    if "type" not in clean and "properties" in clean:
        clean["type"] = "object"
    return clean


def _extract_hapi_url(text: str) -> str | None:
    import re
    m = re.search(r"https://hapi\.fhir\.org/baseR4/RiskAssessment/\d+", text or "")
    return m.group(0) if m else None


def _extract_fhir_id(text: str) -> str | None:
    import re
    m = re.search(r"RiskAssessment/(\d+)", text or "")
    return m.group(1) if m else None


async def main() -> int:
    prompt = sys.argv[1] if len(sys.argv) > 1 else (
        "I am Africa CDC. We have budget for 10 sentinel sites this quarter, "
        "prioritising H5N1 and Ebola. Where should we place them, and how "
        "much uncertainty reduction does that buy us?"
    )

    try:
        result = await run_via_adk(prompt)
        path = "google-adk"
    except Exception as exc:
        logger.info("ADK path unavailable (%s); falling back to genai", exc)
        result = await run_via_genai_fallback(prompt)
        path = "google-genai"

    print(f"\n=== AqtaBio briefing agent · path={path} · {result.latency_ms} ms ===")
    print(f"\nQ: {result.prompt}\n")
    print(result.answer)
    print(f"\nTools called: {', '.join(result.tools_called) or '(none)'}")
    if result.hapi_url:
        print(f"HAPI URL    : {result.hapi_url}")
        print(f"Verify with : curl -H 'Accept: application/fhir+json' {result.hapi_url}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
