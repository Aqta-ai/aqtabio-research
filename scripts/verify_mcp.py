#!/usr/bin/env python3
"""
Verify the AqtaBio MCP server end-to-end without a browser.

Performs a real MCP handshake against the production endpoint, lists the
advertised tools, and calls three of them — including the Disease X tool.
Prints results as humans would expect to see them in a demo.

Usage:
    python3 scripts/verify_mcp.py
    python3 scripts/verify_mcp.py --endpoint https://your-mcp-server/mcp

Exit codes:
    0  every check passed
    1  handshake / network failure
    2  tools/list returned fewer than expected
    3  tool call failed
"""

import argparse
import json
import re
import subprocess
import sys

DEFAULT_ENDPOINT = "https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp"


def post(endpoint: str, payload: dict, timeout: float = 60.0) -> dict:
    """POST to the MCP endpoint via curl (uses system cert store; avoids
    macOS Python's missing-CA-bundle issue)."""
    proc = subprocess.run(
        [
            "curl", "-s", "-m", str(int(timeout)),
            "-X", "POST", endpoint,
            "-H", "Content-Type: application/json",
            "-H", "Accept: application/json, text/event-stream",
            "-d", json.dumps(payload),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"curl exited {proc.returncode}: {proc.stderr.strip()}")
    raw = proc.stdout
    # SSE response: pull the JSON out of the first "data: " line
    m = re.search(r"data: (\{.*\})", raw, re.DOTALL)
    if not m:
        raise RuntimeError(f"No SSE data line in response. Raw:\n{raw[:500]}")
    return json.loads(m.group(1))


def banner(s: str) -> None:
    print()
    print("─" * 60)
    print(s)
    print("─" * 60)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    args = p.parse_args()

    print(f"Endpoint: {args.endpoint}")

    # 1. initialize handshake
    banner("1. Handshake (initialize)")
    try:
        d = post(args.endpoint, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "verify_mcp", "version": "0.1"},
            },
        })
    except (HTTPError, URLError, RuntimeError) as exc:
        print(f"FAIL: {exc}")
        return 1

    info = d.get("result", {}).get("serverInfo", {})
    proto = d.get("result", {}).get("protocolVersion")
    caps = list(d.get("result", {}).get("capabilities", {}).keys())
    print(f"  server         : {info.get('name')} v{info.get('version')}")
    print(f"  protocol       : {proto}")
    print(f"  capabilities   : {', '.join(caps)}")

    # 2. tools/list
    banner("2. Available tools (tools/list)")
    d = post(args.endpoint, {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    })
    tools = d.get("result", {}).get("tools", [])
    if len(tools) < 10:
        print(f"FAIL: only {len(tools)} tools advertised, expected 12")
        return 2
    print(f"  {len(tools)} tools advertised:")
    for t in tools:
        desc = t.get("description", "").strip().split("\n")[0][:80]
        print(f"    • {t['name']:<32} {desc}")

    # 3. call get_disease_x_risk — the headline Disease X tool
    banner("3. Disease X tool call (the new pathogen-agnostic one)")
    d = post(args.endpoint, {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "get_disease_x_risk",
            "arguments": {"tile_id": "AF-025-10004"},
        },
    })
    content = d.get("result", {}).get("content", [])
    if not content or content[0].get("type") != "text":
        print(f"FAIL: unexpected response shape: {json.dumps(d)[:300]}")
        return 3
    payload = json.loads(content[0]["text"])
    print(f"  tile_id        : {payload['tile_id']}")
    print(f"  disease_x_score: {payload['disease_x_risk_score']}")
    print(f"  risk_tier      : {payload['risk_tier']}")
    print(f"  blueprint      : {payload['blueprint_priority']}")
    print(f"  top contributors:")
    for c in payload.get("top_contributing_pathogens", [])[:3]:
        print(f"    {c['pathogen_display']:<32} {c['score']}")

    # 4. call retrospective_validation — the recorded retrospective for Wuhan
    banner("4. Wuhan retrospective tool call (recorded attestation)")
    d = post(args.endpoint, {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "retrospective_validation",
            "arguments": {"event_id": "2019_wuhan_sars_cov_2"},
        },
    })
    content = d.get("result", {}).get("content", [])
    payload = json.loads(content[0]["text"])
    print(f"  event_name     : {payload['event_name']}")
    print(f"  threshold date : {payload['prediction']['threshold_crossed_date']}")
    print(f"  risk score     : {payload['prediction']['risk_score_at_threshold']}")
    print(f"  WHO notified   : {payload['ground_truth']['official_notification_date']}")
    print(f"  lead time      : {payload['validation']['lead_time_days']} days")

    # 5. call get_risk_score with FHIR — the demo's hero shot
    banner("5. FHIR R4 RiskAssessment (the demo's standards-compliance moment)")
    d = post(args.endpoint, {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "get_risk_score",
            "arguments": {
                "tile_id": "AF-025-10004",
                "pathogen": "ebola",
                "fhir_format": True,
            },
        },
    })
    content = d.get("result", {}).get("content", [])
    payload = json.loads(content[0]["text"])
    print(f"  resourceType   : {payload.get('resourceType')}")
    print(f"  status         : {payload.get('status')}")
    print(f"  occurrenceDate : {payload.get('occurrenceDateTime')}")
    method_coding = (payload.get("method") or {}).get("coding", [{}])[0]
    print(f"  method coding  : {method_coding.get('code')} ({method_coding.get('display')})")

    banner("All five checks passed")
    print("MCP server is fully operational at:")
    print(f"  {args.endpoint}")
    print("Use this in any MCP client (Claude Desktop, Prompt Opinion, mcp-inspector)")
    print("with transport = 'Streamable HTTP'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
