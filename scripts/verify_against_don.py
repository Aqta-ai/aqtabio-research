#!/usr/bin/env python3
"""
verify_against_don.py — match a WHO Disease Outbreak News (or any
public outbreak notification) against AqtaBio's prior public
commitment for the affected tile.

Usage
-----

    python3 scripts/verify_against_don.py \\
        --tile-id AF-025-10010 \\
        --pathogen ebola \\
        --notification-date 2026-05-30

Output is JSON. The script does NOT call the live MCP; it reads
the append-only `commitments/` folder in this repository, finds
the most recent file whose evaluation window started on or before
the notification date, and reports the matching tile entry (or
none).

Verification protocol
---------------------

Given an outbreak notification:

  1. Identify the AqtaBio 25 km tile that contains the centroid
     of the affected location. Tile ids look like
     `AF-025-10010` (Africa, 25 km grid, index 10010).
  2. Note the public-notification date (the WHO DON publish date,
     the ECDC weekly bulletin date, or the national MoH
     declaration date — whichever is publicly verifiable and
     earliest).
  3. Run this script with the tile-id, pathogen-id, and
     notification date.
  4. The script prints:
       - the commitment file the lookup used,
       - whether the tile was on the commitment for that pathogen,
       - the lead time in days if it was,
       - the risk-score and confidence band recorded then.

The script intentionally does no remote I/O. The git history
of `commitments/` is the source of truth.

Exit codes
----------

  0   verification ran (whether the tile was committed or not)
  2   no commitment file exists on or before the notification date
  3   the requested pathogen was not in the commitment's
      `pathogens_covered` list (e.g. mpox, nipah, hantavirus
      pending tile seeding)
  4   bad arguments
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import sys
from typing import Optional


def _commitments_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "commitments"))


def _load_all_commitments() -> list[dict]:
    pattern = os.path.join(_commitments_dir(), "*.json")
    files = sorted(glob.glob(pattern))
    out: list[dict] = []
    for path in files:
        try:
            with open(path) as fh:
                obj = json.load(fh)
            obj["__path__"] = os.path.relpath(path, os.path.dirname(_commitments_dir()))
            out.append(obj)
        except Exception as exc:
            print(f"warning: skipping malformed {path}: {exc}", file=sys.stderr)
    return out


def _most_recent_before(commitments: list[dict], notification_date: datetime.date) -> Optional[dict]:
    """Find the commitment with the latest generated_at that is on or
    before the notification date.

    Filtering on generated_at (NOT evaluation_window.start) is what makes
    the verification honest: the commitment must actually have been made
    before the notification. Filtering on evaluation_window.start would
    let a commitment from later that same Monday match a notification
    earlier in the week, producing a fake negative lead time.
    """
    candidates = []
    for c in commitments:
        gen_str = c.get("generated_at")
        if not gen_str:
            continue
        gen_date = datetime.date.fromisoformat(gen_str[:10])
        if gen_date <= notification_date:
            candidates.append((gen_date, c))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p[0])
    return candidates[-1][1]


def _entry_for_tile(commitment: dict, tile_id: str, pathogen: str) -> Optional[dict]:
    for t in commitment.get("tiles", []):
        if t.get("tile_id") == tile_id and t.get("pathogen") == pathogen:
            return t
    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tile-id", required=True, help="AqtaBio tile-id, e.g. AF-025-10010")
    p.add_argument("--pathogen", required=True, help="Pathogen id (ebola, h5n1, cchfv, wnv, sea-cov)")
    p.add_argument("--notification-date", required=True, help="YYYY-MM-DD of the public notification")
    p.add_argument(
        "--source",
        default=None,
        help="Optional URL or citation for the source-of-truth notification",
    )
    args = p.parse_args()

    try:
        notif_date = datetime.date.fromisoformat(args.notification_date)
    except ValueError:
        print("notification-date must be YYYY-MM-DD", file=sys.stderr)
        return 4

    commitments = _load_all_commitments()
    if not commitments:
        print(json.dumps({"status": "error", "reason": "no commitment files found"}, indent=2))
        return 2

    chosen = _most_recent_before(commitments, notif_date)
    if chosen is None:
        print(json.dumps(
            {
                "status": "no_prior_commitment",
                "notification_date": args.notification_date,
                "tile_id": args.tile_id,
                "pathogen": args.pathogen,
                "earliest_commitment": commitments[0].get("evaluation_window", {}).get("start"),
            },
            indent=2,
        ))
        return 2

    if args.pathogen not in (chosen.get("pathogens_covered") or []):
        print(json.dumps(
            {
                "status": "pathogen_not_covered_in_commitment",
                "commitment_file": chosen["__path__"],
                "pathogen": args.pathogen,
                "pathogens_covered": chosen.get("pathogens_covered"),
                "pathogens_pending_tile_seeding": chosen.get("pathogens_pending_tile_seeding"),
            },
            indent=2,
        ))
        return 3

    entry = _entry_for_tile(chosen, args.tile_id, args.pathogen)
    generated_at = chosen.get("generated_at")
    gen_date = datetime.date.fromisoformat(generated_at[:10]) if generated_at else None
    lead_days = (notif_date - gen_date).days if gen_date else None

    if entry is None:
        result = {
            "status": "miss_or_coverage_gap",
            "interpretation": (
                "The requested tile was NOT on AqtaBio's commitment for this "
                "pathogen on the most recent commitment date before the "
                "notification. This is either a miss (the tile was scored but "
                "not in the top-N for the pathogen) or a coverage gap (the "
                "tile was not in the seeded production pool). Inspect "
                "`commitments/" + chosen.get("iso_week", "") + ".json` to confirm."
            ),
            "commitment_file": chosen["__path__"],
            "commitment_iso_week": chosen.get("iso_week"),
            "commitment_generated_at": generated_at,
            "lead_time_days_if_committed": lead_days,
            "tile_id": args.tile_id,
            "pathogen": args.pathogen,
            "notification_date": args.notification_date,
            "source": args.source,
        }
        print(json.dumps(result, indent=2))
        return 0

    result = {
        "status": "hit",
        "interpretation": (
            f"AqtaBio committed publicly on {generated_at} that tile "
            f"{args.tile_id} was rank-{entry.get('rank')} for {args.pathogen} "
            f"with risk score {entry.get('risk_score')} (band "
            f"{entry.get('p10')}–{entry.get('p90')}). The public "
            f"notification followed {lead_days} days later."
        ),
        "commitment_file": chosen["__path__"],
        "commitment_iso_week": chosen.get("iso_week"),
        "commitment_generated_at": generated_at,
        "model_image_digest": (chosen.get("model") or {}).get("image_digest"),
        "lead_time_days": lead_days,
        "tile_id": args.tile_id,
        "pathogen": args.pathogen,
        "rank_in_commitment": entry.get("rank"),
        "risk_score_at_commitment": entry.get("risk_score"),
        "p10_at_commitment": entry.get("p10"),
        "p90_at_commitment": entry.get("p90"),
        "top_drivers_at_commitment": entry.get("top_drivers"),
        "notification_date": args.notification_date,
        "source": args.source,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
