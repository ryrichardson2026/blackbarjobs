#!/usr/bin/env python3
"""
bbj_wh_hub_feeds.py  ·  Derive Chicago warehouse hub feeds from board.json

The warehouse hub feeds are derived from feed/board.json (the current, fresh pull the
board actually displays) rather than the full active-jobs table, so a hub's feed can never
contain jobs the board does not show. That freshness parity matters for the JobPosting
schema (the Google Jobs surface, ~79% of clicks): baking a listing the board no longer
shows risks an expired posting.

Matching mirrors js/bbj-board.js exactly so feed count == board display count:
  - roles  (associate/forklift/package-handler): title + company     (deriveRoles)
  - shifts/attributes (overnight/part-time/weekend/hiring-immediately/pay-weekly):
    title + company + description                                     (deriveShifts, warehouse)
part-time also matches when the schedule/job_type says "part" (the board's jt hook).

Only the nine shippable hubs are written. night-shift (synonym of overnight),
no-experience and entry-level (thin and identical) are intentionally NOT derived; any stale
feed files for them are removed so the gate/build never pick them up.

Usage:  python bbj_wh_hub_feeds.py            # reads feed/board.json, writes feed/chicago/warehouse/*.json
"""

import json, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
BOARD = REPO / "feed" / "board.json"
OUT_DIR = REPO / "feed" / "chicago" / "warehouse"
METRO = "chicago"
VERTICAL = "warehouse"

# Regexes copied from js/bbj-board.js TAXONOMY / SHIFTS (case-insensitive).
ROLE_RE = {
    "associate":       r"warehouse associate|warehouse worker|warehouse|picker|packer|material handler|distribution|fulfillment",
    "forklift":        r"forklift|lift truck|reach truck|cherry picker|order picker",
    "package-handler": r"package handler|package|parcel|sorter|loader|unloader|\bdock\b",
}
SHIFT_RE = {
    "overnight":          r"overnight|graveyard|11:00\s*pm|11pm|3:00pm-11|10pm|grave shift|\bnight\b",
    "part-time":          r"part[\s-]?time",
    "weekend":            r"weekend|saturday|sunday",
    "hiring-immediately": r"immediate|hiring now|now hiring|urgently hiring|start (?:today|now|this week)",
    "pay-weekly":         r"weekly pay|paid weekly|pays? weekly|weekly paycheck|paid every week",
}

# hub feed key slug -> (kind, key). kind: "metro" | "role" | "shift".
HUBS = [
    ("warehouse-jobs",                    "metro", None),
    ("warehouse-associate-jobs",          "role",  "associate"),
    ("forklift-operator-jobs",            "role",  "forklift"),
    ("package-handler-jobs",              "role",  "package-handler"),
    ("overnight-warehouse-jobs",          "shift", "overnight"),
    ("part-time-warehouse-jobs",          "shift", "part-time"),
    ("weekend-warehouse-jobs",            "shift", "weekend"),
    ("warehouse-jobs-hiring-immediately", "shift", "hiring-immediately"),
    ("warehouse-jobs-that-pay-weekly",    "shift", "pay-weekly"),
]
# Feeds that must NOT exist (dropped hubs): removed if present so nothing downstream ships them.
DROP = ["night-shift-warehouse-jobs", "no-experience-warehouse-jobs", "entry-level-warehouse-jobs"]


def role_text(j):
    return ((j.get("title") or "") + " " + (j.get("company") or "")).lower()


def shift_text(j):
    return (role_text(j) + " " + str(j.get("description") or "")).lower()


def match_role(j, key):
    return re.search(ROLE_RE[key], role_text(j)) is not None


def match_shift(j, key):
    if re.search(SHIFT_RE[key], shift_text(j)):
        return True
    if key == "part-time":                                   # board's jt:'part' hook
        return "part" in (j.get("schedule") or j.get("job_type") or "").lower()
    return False


def main():
    if not BOARD.exists():
        print("feed/board.json missing; run the snapshot first.", file=sys.stderr); sys.exit(1)
    board = json.loads(BOARD.read_text(encoding="utf-8"))
    generated = board.get("generated") or ""
    metro_jobs = [j for j in (board.get("jobs") or [])
                  if j.get("vertical") == VERTICAL and (j.get("market") or "").lower() == METRO]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Chicago %s metro set from board.json: %d jobs" % (VERTICAL, len(metro_jobs)))
    for slug, kind, key in HUBS:
        if kind == "metro":
            jobs = list(metro_jobs)
            target = "city"
        elif kind == "role":
            jobs = [j for j in metro_jobs if match_role(j, key)]
            target = "city-role"
        else:
            jobs = [j for j in metro_jobs if match_shift(j, key)]
            target = "city-role"
        out = {"generated": generated, "page": "chicago/warehouse/" + slug, "market": "Chicago",
               "target": target, "count": len(jobs), "exact": len(jobs), "jobs": jobs}
        (OUT_DIR / (slug + ".json")).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  %-38s exact=%d" % (slug, len(jobs)))

    for slug in DROP:
        fp = OUT_DIR / (slug + ".json")
        if fp.exists():
            fp.unlink()
            print("  removed dropped feed: %s" % slug)


if __name__ == "__main__":
    main()
