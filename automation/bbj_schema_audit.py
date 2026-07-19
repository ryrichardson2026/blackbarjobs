#!/usr/bin/env python3
"""
bbj_schema_audit.py  ·  JobPosting coverage audit (read only)

Reports which HTML pages carrying a live feed (BBJ_FEED_KEY) emit JobPosting
JSON-LD, which are correctly excluded (hub / utility pages that carry
CollectionPage / ItemList and must never carry JobPosting), and which are a
COVERAGE GAP: a real feed page that has never emitted JobPosting and is therefore
ineligible for Google Jobs.

A gap page is classified as:
  - fixable now (feed has jobs)      feed/<key>.json exists and has >=1 job
  - feed file missing                no feed/<key>.json on disk
  - feed present but no usable job   feed exists but its jobs array is empty

Read only: it never writes HTML. With --json it writes the gap list (paths + key
+ market + job count) so the migrate/fill step can operate on an explicit set.

Usage (from repo root):
  python automation/bbj_schema_audit.py --repo . --json /tmp/schema-gap.json
"""

import argparse, json, os, re, sys
from collections import Counter

SCRIPT_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
TYPE_RE = re.compile(r'"@type"\s*:\s*"([^"]+)"')
KEY_RE = re.compile(r'BBJ_FEED_KEY\s*=\s*"([^"]+)"')

def top_types(html):
    return [TYPE_RE.search(m.group(1)).group(1)
            for m in SCRIPT_RE.finditer(html) if TYPE_RE.search(m.group(1))]

def is_hub_or_utility(rel, types):
    """Hub / utility pages that legitimately never carry JobPosting: anything that
    already carries CollectionPage/ItemList, plus market index and job-board utility
    pages. These are excluded from the gap, not fixed."""
    if "CollectionPage" in types or "ItemList" in types:
        return True
    base = rel.rsplit("/", 1)[-1]
    if base == "index.html" or base.endswith("-index.html"):
        return True
    if base in ("job-board.html",):
        return True
    return False

def market_of(rel):
    return rel.split("/")[0] if "/" in rel else "(root)"

def main():
    ap = argparse.ArgumentParser(description="BBJ JobPosting coverage audit (read only)")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--json", help="write the gap list to this path")
    args = ap.parse_args()

    feed_pages = 0
    emit, excluded, gap = [], [], []
    for root, dirs, files in os.walk(args.repo):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".vercel")]
        for f in sorted(files):
            if not f.endswith(".html"):
                continue
            full = os.path.join(root, f)
            with open(full, encoding="utf-8", newline="") as fh:
                html = fh.read()
            m = KEY_RE.search(html)
            if not m:
                continue
            feed_pages += 1
            rel = os.path.relpath(full, args.repo).replace(os.sep, "/")
            types = top_types(html)
            if "JobPosting" in types:
                emit.append(rel)
            elif is_hub_or_utility(rel, types):
                excluded.append(rel)
            else:
                gap.append((rel, m.group(1)))

    # classify the gap by feed availability
    feed_dir = os.path.join(args.repo, "feed")
    fixable, feed_missing, no_usable = [], [], []
    gap_records = []
    for rel, key in sorted(gap):
        fp = os.path.join(feed_dir, key + ".json")
        n_jobs = None
        if not os.path.exists(fp):
            feed_missing.append(rel)
            bucket = "feed_missing"
        else:
            with open(fp, encoding="utf-8") as fh:
                jobs = (json.load(fh).get("jobs") or [])
            n_jobs = len(jobs)
            if n_jobs == 0:
                no_usable.append(rel)
                bucket = "no_usable_job"
            else:
                fixable.append(rel)
                bucket = "fixable"
        gap_records.append({"path": rel, "key": key, "market": market_of(rel),
                            "jobs": n_jobs, "bucket": bucket})

    gap_by_market = Counter(r["market"] for r in gap_records)

    print("HTML pages carrying BBJ_FEED_KEY : %d" % feed_pages)
    print("already emit JobPosting          : %d" % len(emit))
    print("correctly excluded (hub/utility) : %d" % len(excluded))
    print("COVERAGE GAP                     : %d" % len(gap_records))
    print("  fixable now (feed has jobs)    : %d" % len(fixable))
    print("  feed file missing              : %d" % len(feed_missing))
    print("  feed present but no usable job : %d" % len(no_usable))
    print("gap by market: " + ", ".join("%s %d" % (m, n)
          for m, n in sorted(gap_by_market.items(), key=lambda t: (-t[1], t[0]))))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"feed_pages": feed_pages, "emit": len(emit),
                       "excluded": sorted(excluded), "gap": gap_records},
                      fh, indent=2)
        print("wrote gap list -> %s" % args.json)

    return 0

if __name__ == "__main__":
    sys.exit(main())
