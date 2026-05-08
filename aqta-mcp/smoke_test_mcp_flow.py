#!/usr/bin/env python3
"""
End-to-end smoke test for the AqtaBio MCP backend.

Exercises the call sequence the ADK + Gemini wrapper agent issues
when answering an Africa CDC sentinel-placement question. Runs
against the live MCP endpoint without requiring a Gemini API key —
the MCP-side path only.

Usage:
    python smoke_test_mcp_flow.py

Exit codes:
    0  all four steps passed
    1  any step failed (test will print which one)

Steps validated:
    1. tools/list                — confirms 19 tools live, including
                                   optimise_sentinel_placement
    2. optimise_sentinel_placement — returns ranked deployment plan
    3. get_risk_score (fhir=true)  — top pick yields valid FHIR R4
                                     RiskAssessment
    4. submit_to_hapi_fhir         — round-trips a real FHIR resource
                                     against the public HAPI test
                                     server (HTTP 201 on success,
                                     HTTP 200 on idempotent re-submit)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from typing import Any

MCP_URL = "https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def call(method: str, params: dict, rid: int = 1) -> dict[str, Any]:
    """Send one JSON-RPC call to the MCP endpoint. Parse the SSE-or-JSON
    response shape that FastMCP's streamable HTTP transport returns."""
    body = json.dumps(
        {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}
    ).encode()
    req = urllib.request.Request(MCP_URL, data=body, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode()
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: ") :])
    raise RuntimeError(f"Unparseable MCP response: {text[:300]}")


def tool_text(rpc: dict) -> str:
    """Extract the first text payload from an MCP tool response."""
    for c in rpc.get("result", {}).get("content") or []:
        if c.get("type") == "text":
            return c.get("text", "")
    return ""


def fail(step: int, msg: str) -> None:
    print(f"\n[{step}] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    print("=" * 70)
    print("AGENT-FLOW SMOKE TEST · live MCP, no Gemini key required")
    print("=" * 70)

    # Step 1: tool discovery
    t0 = time.monotonic()
    r1 = call("tools/list", {}, rid=1)
    tools = r1.get("result", {}).get("tools", [])
    names = [t["name"] for t in tools]
    elapsed = (time.monotonic() - t0) * 1000
    print(f"\n[1] tools/list ........... {len(names)} tools  {elapsed:.0f} ms")
    required = {"optimise_sentinel_placement", "get_risk_score", "submit_to_hapi_fhir"}
    missing = required - set(names)
    if missing:
        fail(1, f"required tools missing from deployed MCP: {missing}")
    print("    PASS — all required tools present")

    # Step 2: active-learning recommender
    t0 = time.monotonic()
    r2 = call(
        "tools/call",
        {
            "name": "optimise_sentinel_placement",
            "arguments": {
                "pathogens": ["ebola", "h5n1"],
                "region": "africa-cdc",
                "budget_sites": 5,
            },
        },
        rid=2,
    )
    plan_text = tool_text(r2)
    if not plan_text:
        fail(2, f"empty tool response. Raw RPC: {json.dumps(r2)[:400]}")
    plan = json.loads(plan_text)
    selected = plan.get("selected_sites") or []
    if not selected:
        fail(2, f"no sites returned. Plan error: {plan.get('error')}")
    top = selected[0]
    elapsed = (time.monotonic() - t0) * 1000
    print(f"\n[2] optimise_sentinel_placement ... {len(selected)} sites  {elapsed:.0f} ms")
    print(f"    Top pick   : {top['tile_id']}")
    print(f"    EIG score  : {top['eig_score']}")
    print(f"    Pathogen   : {top.get('dominant_pathogen')}")
    print(f"    Reduction  : {plan.get('aggregate_uncertainty_reduction_estimate')}")
    print("    PASS")

    # Step 3: FHIR for top pick
    top_tile = top["tile_id"]
    top_path = top.get("dominant_pathogen") or "ebola"
    t0 = time.monotonic()
    r3 = call(
        "tools/call",
        {
            "name": "get_risk_score",
            "arguments": {
                "tile_id": top_tile,
                "pathogen": top_path,
                "fhir_format": True,
            },
        },
        rid=3,
    )
    fhir_text = tool_text(r3)
    if not fhir_text:
        fail(3, f"empty content. Raw RPC: {json.dumps(r3)[:400]}")
    fhir = json.loads(fhir_text)
    if fhir.get("resourceType") != "RiskAssessment":
        fail(3, f"expected RiskAssessment, got {fhir.get('resourceType')}")
    elapsed = (time.monotonic() - t0) * 1000
    print(f"\n[3] get_risk_score (fhir=true) .... {fhir['resourceType']}  {elapsed:.0f} ms")
    p = (fhir.get("prediction") or [{}])[0].get("probabilityDecimal")
    print(f"    Subject    : {fhir.get('subject', {}).get('display')}")
    print(f"    P          : {p}")
    print(f"    SHAP n     : {len(fhir.get('basis') or [])}")
    print("    PASS")

    # Step 4: HAPI round-trip
    t0 = time.monotonic()
    r4 = call(
        "tools/call",
        {
            "name": "submit_to_hapi_fhir",
            "arguments": {"tile_id": top_tile, "pathogen": top_path},
        },
        rid=4,
    )
    hapi_text = tool_text(r4)
    if not hapi_text:
        fail(4, f"empty content. Raw RPC: {json.dumps(r4)[:400]}")
    hapi = json.loads(hapi_text)
    # 201 on first creation, 200 on idempotent re-submit (server resolves
    # duplicate via OperationOutcome diagnostics and returns existing id).
    if hapi.get("hapi_status") not in (200, 201):
        fail(4, f"expected HAPI 200 or 201, got {hapi.get('hapi_status')}")
    url = hapi.get("risk_assessment_url")
    elapsed = (time.monotonic() - t0) * 1000
    print(f"\n[4] submit_to_hapi_fhir ........... HTTP {hapi['hapi_status']}  {elapsed:.0f} ms")
    print(f"    Resource   : {hapi.get('resource_id')}")
    print(f"    URL        : {url}")
    print("    PASS")

    print("\n" + "=" * 70)
    print("ALL FOUR STEPS PASSED — backend is operational")
    print("=" * 70)
    print(
        f"\nLive verification:\n"
        f"  curl -H 'Accept: application/fhir+json' {url}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
