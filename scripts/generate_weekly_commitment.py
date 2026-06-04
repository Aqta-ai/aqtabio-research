#!/usr/bin/env python3
"""
Generate a weekly commitment file from the live AqtaBio MCP.

Queries the production MCP for the top-ranked tiles per pathogen, formats
them into a commitments/YYYY-WNN.json file that matches commitments/SCHEMA.md,
and (optionally) signs the canonical payload with an Ed25519 key.

Intended to be run on Monday morning UTC. The file is idempotent: if this
week's commitment already exists on disk, the script exits cleanly without
overwriting it (commitments are append-only).

This is a current-state attestation: the model's top-risk tiles for the
named pathogens at the moment the script runs, not a backdated forecast.

Usage:
    python3 scripts/generate_weekly_commitment.py
    python3 scripts/generate_weekly_commitment.py --endpoint https://.../mcp
    python3 scripts/generate_weekly_commitment.py --week 2026-W23 --dry-run

Env vars:
    AQTABIO_COMMITMENT_PRIVATE_KEY_B64
        Optional. Base64-encoded Ed25519 private key (32 bytes raw seed).
        When set, the script adds a `signature` block to the file.

Exit codes:
    0  file written (or already on record for this week)
    1  MCP unreachable / handshake failed
    2  insufficient tile data returned
    3  write failure
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_ENDPOINT = "https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp"
DEFAULT_IMAGE_DIGEST = (
    "sha256:5f1e79d3d36fc66378a24c11a6261f8d8679f34005b75ae9a11463acacbfb4d9"
)
TOP_N_PER_PATHOGEN = 5
TILE_POOL_LIMIT = 20
REPO_ROOT = Path(__file__).resolve().parent.parent
COMMITMENTS_DIR = REPO_ROOT / "commitments"

HONEST_CAVEATS = [
    "Risk score is population-level for a 25 km tile, not a per-patient diagnostic.",
    "Coverage is sparse (578 production tiles); outbreaks in unseeded tiles record as `coverage_gap`, not `miss`.",
    "No claim that an outbreak WILL occur in the listed tiles; the commitment is that AqtaBio considered these tiles highest-risk for the named pathogen during the named window.",
]


def post(endpoint: str, payload: dict, timeout: int = 60) -> dict:
    """POST a JSON-RPC payload to the MCP via curl and parse the SSE body."""
    proc = subprocess.run(
        [
            "curl", "-s", "-m", str(timeout),
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
    match = re.search(r"data: (\{.*\})", proc.stdout, re.DOTALL)
    if not match:
        raise RuntimeError(f"no SSE data line in response: {proc.stdout[:300]}")
    return json.loads(match.group(1))


def call_tool(endpoint: str, name: str, arguments: dict, rpc_id: int) -> dict:
    """Invoke an MCP tool and return the parsed text payload."""
    resp = post(endpoint, {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    content = resp.get("result", {}).get("content", [])
    if not content or content[0].get("type") != "text":
        raise RuntimeError(f"unexpected MCP response for {name}: {json.dumps(resp)[:300]}")
    return json.loads(content[0]["text"])


def iso_week_window(today: dt.date) -> tuple[str, dt.date, dt.date]:
    """Return ('YYYY-WNN', monday, sunday) for the ISO week containing today."""
    year, week, _ = today.isocalendar()
    monday = dt.date.fromisocalendar(year, week, 1)
    sunday = dt.date.fromisocalendar(year, week, 7)
    return f"{year}-W{week:02d}", monday, sunday


def parse_iso_week(label: str) -> tuple[str, dt.date, dt.date]:
    """Parse an explicit 'YYYY-WNN' override."""
    m = re.fullmatch(r"(\d{4})-W(\d{2})", label)
    if not m:
        raise ValueError(f"invalid ISO week label: {label!r} (expected YYYY-WNN)")
    year, week = int(m.group(1)), int(m.group(2))
    monday = dt.date.fromisocalendar(year, week, 1)
    sunday = dt.date.fromisocalendar(year, week, 7)
    return f"{year}-W{week:02d}", monday, sunday


def fetch_pathogens(endpoint: str) -> tuple[list[str], list[str]]:
    """Return (covered, pending) pathogen IDs from list_pathogens."""
    data = call_tool(endpoint, "list_pathogens", {}, rpc_id=10)
    covered, pending = [], []
    for p in data.get("pathogens", []):
        if p.get("prediction_status") == "live":
            covered.append(p["id"])
        elif p.get("prediction_status") == "pending_tile_seeding":
            pending.append(p["id"])
    return covered, pending


def fetch_top_tiles(endpoint: str, pathogen: str, rpc_id: int) -> list[dict]:
    """Fetch the top-N tiles for a pathogen, enriched with per-tile detail."""
    pool = call_tool(
        endpoint,
        "get_top_risk_tiles",
        {"pathogen": pathogen, "limit": TILE_POOL_LIMIT},
        rpc_id=rpc_id,
    )
    candidates = pool.get("top_tiles", [])
    # Selection rule from SCHEMA.md: prefer non-saturated (p90 - p10 > 0.001).
    non_saturated = [t for t in candidates if (t.get("p90", 0) - t.get("p10", 0)) > 0.001]
    chosen = non_saturated[:TOP_N_PER_PATHOGEN]
    if len(chosen) < TOP_N_PER_PATHOGEN:
        # Top up from saturated tiles so the file always has 5 per pathogen.
        seen = {t["tile_id"] for t in chosen}
        for t in candidates:
            if t["tile_id"] not in seen:
                chosen.append(t)
                if len(chosen) >= TOP_N_PER_PATHOGEN:
                    break

    entries: list[dict] = []
    for rank, tile in enumerate(chosen[:TOP_N_PER_PATHOGEN], start=1):
        detail = call_tool(
            endpoint,
            "get_risk_score",
            {"tile_id": tile["tile_id"], "pathogen": pathogen},
            rpc_id=rpc_id * 100 + rank,
        )
        unsigned = detail.get("unsigned_payload", detail)
        p10 = unsigned.get("confidence", {}).get("p10", tile.get("p10"))
        p90 = unsigned.get("confidence", {}).get("p90", tile.get("p90"))
        drivers = [
            d.get("feature_name") if isinstance(d, dict) else d
            for d in unsigned.get("top_drivers", [])
        ][:3]
        entries.append({
            "pathogen": pathogen,
            "rank": rank,
            "tile_id": tile["tile_id"],
            "country_iso3": tile.get("country_iso3"),
            "region": tile.get("region"),
            "month": unsigned.get("month"),
            "risk_score": unsigned.get("risk_score", tile.get("risk_score")),
            "p10": p10,
            "p90": p90,
            "uncertainty_band": round((p90 or 0) - (p10 or 0), 4),
            "top_drivers": drivers,
        })
    return entries


def canonical_json(payload: dict) -> bytes:
    """Stable byte form for hashing/signing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def maybe_sign(payload_bytes: bytes) -> dict | None:
    """Sign the canonical payload if a key is present in the environment."""
    seed_b64 = os.environ.get("AQTABIO_COMMITMENT_PRIVATE_KEY_B64")
    if not seed_b64:
        return None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        print("warning: cryptography not installed; skipping signature", file=sys.stderr)
        return None

    seed = base64.b64decode(seed_b64)
    if len(seed) != 32:
        print(f"warning: AQTABIO_COMMITMENT_PRIVATE_KEY_B64 is {len(seed)} bytes, expected 32; skipping signature", file=sys.stderr)
        return None
    key = Ed25519PrivateKey.from_private_bytes(seed)
    sig = key.sign(payload_bytes)
    pub_spki = key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fingerprint = hashlib.sha256(pub_spki).hexdigest()[:12]
    return {
        "algorithm": "ed25519",
        "public_key_spki_b64": base64.b64encode(pub_spki).decode("ascii"),
        "key_fingerprint": fingerprint,
        "signature_b64": base64.b64encode(sig).decode("ascii"),
    }


def build_commitment(endpoint: str, iso_week: str, start: dt.date, end: dt.date) -> dict:
    covered, pending = fetch_pathogens(endpoint)
    if not covered:
        raise RuntimeError("MCP returned no live pathogens; aborting")

    tiles: list[dict] = []
    for idx, pathogen in enumerate(covered, start=1):
        tiles.extend(fetch_top_tiles(endpoint, pathogen, rpc_id=100 + idx))

    if len(tiles) < TOP_N_PER_PATHOGEN:
        raise RuntimeError(f"only {len(tiles)} tile entries assembled; expected >= {TOP_N_PER_PATHOGEN}")

    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {
        "iso_week": iso_week,
        "generated_at": generated_at,
        "evaluation_window": {"start": start.isoformat(), "end": end.isoformat()},
        "model": {
            "name": "AqtaBio XGBoost ensemble",
            "version": "v0.1.0",
            "image_digest": DEFAULT_IMAGE_DIGEST,
            "mcp_endpoint": endpoint,
        },
        "method": {
            "tile_pool": f"MCP get_top_risk_tiles(pathogen, limit={TILE_POOL_LIMIT})",
            "selection": "highest risk_score, prefer non-saturated (p90 - p10 > 0.001)",
            "top_n_per_pathogen": TOP_N_PER_PATHOGEN,
        },
        "pathogens_covered": covered,
        "pathogens_pending_tile_seeding": pending,
        "tiles": tiles,
        "honest_caveats": HONEST_CAVEATS,
    }
    payload["content_hash_sha256"] = hashlib.sha256(canonical_json(payload)).hexdigest()
    sig = maybe_sign(canonical_json({k: v for k, v in payload.items() if k != "content_hash_sha256"}))
    if sig:
        payload["signature"] = sig
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="MCP endpoint URL")
    parser.add_argument("--week", default=None, help="ISO week override, e.g. 2026-W23 (default: current week UTC)")
    parser.add_argument("--dry-run", action="store_true", help="print the file to stdout instead of writing it")
    args = parser.parse_args()

    today = dt.datetime.now(dt.timezone.utc).date()
    if args.week:
        iso_week, start, end = parse_iso_week(args.week)
    else:
        iso_week, start, end = iso_week_window(today)

    target = COMMITMENTS_DIR / f"{iso_week}.json"
    if target.exists() and not args.dry_run:
        print(f"this week's commitment already on record: {target}")
        return 0

    try:
        payload = build_commitment(args.endpoint, iso_week, start, end)
    except RuntimeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1 if "MCP" in str(exc) or "curl" in str(exc) else 2

    rendered = json.dumps(payload, indent=2) + "\n"
    if args.dry_run:
        sys.stdout.write(rendered)
        return 0

    try:
        COMMITMENTS_DIR.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    except OSError as exc:
        print(f"FAIL: could not write {target}: {exc}", file=sys.stderr)
        return 3

    pathogens = sorted({t["pathogen"] for t in payload["tiles"]})
    print(f"wrote {target}")
    print(f"  iso_week     : {payload['iso_week']}")
    print(f"  window       : {payload['evaluation_window']['start']} to {payload['evaluation_window']['end']}")
    print(f"  pathogens    : {', '.join(pathogens)} ({len(pathogens)})")
    print(f"  tiles ranked : {len(payload['tiles'])}")
    print(f"  content_hash : {payload['content_hash_sha256']}")
    if "signature" in payload:
        print(f"  signed by    : {payload['signature']['key_fingerprint']} (ed25519)")
    else:
        print("  signed by    : (no key in env; unsigned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
