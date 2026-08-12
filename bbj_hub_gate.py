#!/usr/bin/env python3
"""
bbj_hub_gate.py  ·  Build-time hub gate (Notion item 10, never built until Task 2)

Security shipped 24 duplicate clusters: pages whose job set was thin or nearly
identical to a same-metro sibling, cannibalizing each other in search. This gate
refuses to generate such a hub. It runs AFTER the snapshot has written each hub's
feed (feed/<key>.json carries `exact` = the exact-match count and `jobs` = the
ranked set, exact ones first), and BEFORE bbj_build.py writes the page.

Two rules:
  1. min-match  — a hub whose exact-match count < MIN_MATCH is too thin to ship.
  2. dedup      — a hub whose exact job set is >DUP_THRESHOLD Jaccard-identical to
                  an already-passed SAME-TIER sibling is a duplicate. Tiers keep a
                  role page from being killed for overlapping its metro parent:
                  'metro' is exempt; roles dedup against roles, modifiers against
                  modifiers. Each cfg declares its tier via cfg['hub_tier'].

Pure functions + evaluate(); bbj_build.py calls evaluate() and builds only the ok
hubs, printing the block report so the pass/block split is visible.
"""

import json
from pathlib import Path

MIN_MATCH = 10
DUP_THRESHOLD = 0.8
_TIER_ORDER = {"metro": 0, "role": 1, "modifier": 2}


def job_identity(j):
    """Stable identity for a feed job: apply_link if present, else title|company."""
    al = (j.get("apply_link") or "").strip().lower().rstrip("/")
    if al:
        return "a:" + al
    return "t:" + (j.get("title") or "").strip().lower() + "|" + (j.get("company") or "").strip().lower()


def job_id_set(jobs):
    return {job_identity(j) for j in jobs if (j.get("title") or "").strip()}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def tier_of(cfg):
    return cfg.get("hub_tier", "role")


def load_feed(feed_dir, feed_key):
    p = Path(feed_dir) / (feed_key + ".json")
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def evaluate(cfgs, feed_dir, min_match=MIN_MATCH, dup=DUP_THRESHOLD):
    """Return [{cfg, ok, reason, exact, count}] in tier order (metro -> role ->
    modifier). Dedup compares only the EXACT-matched jobs (jobs[:exact]) so metro
    top-ups don't make thin modifiers look alike."""
    items = sorted(cfgs, key=lambda c: _TIER_ORDER.get(tier_of(c), 1))
    passed_by_tier = {}          # tier -> [(slug, exact_id_set)]
    results = []
    for cfg in items:
        fk = cfg.get("feed_key") or cfg["slug"].lstrip("/")
        feed = load_feed(feed_dir, fk)
        if feed is None:
            results.append({"cfg": cfg, "ok": False, "reason": "no feed (snapshot missing)", "exact": 0, "count": 0})
            continue
        exact = int(feed.get("exact") or 0)
        jobs = feed.get("jobs") or []
        ids = job_id_set(jobs[:exact])          # exact matches only, not metro top-ups
        tier = tier_of(cfg)

        if exact < min_match:
            results.append({"cfg": cfg, "ok": False,
                            "reason": "thin: %d exact matches < %d" % (exact, min_match),
                            "exact": exact, "count": len(jobs)})
            continue

        dup_with = None
        if tier != "metro":
            for sib_slug, sib_ids in passed_by_tier.get(tier, []):
                if jaccard(ids, sib_ids) > dup:
                    dup_with = sib_slug
                    break
        if dup_with:
            results.append({"cfg": cfg, "ok": False,
                            "reason": "duplicate job set of %s (Jaccard > %.2f)" % (dup_with, dup),
                            "exact": exact, "count": len(jobs)})
            continue

        passed_by_tier.setdefault(tier, []).append((cfg["slug"], ids))
        results.append({"cfg": cfg, "ok": True, "reason": "ok", "exact": exact, "count": len(jobs)})
    return results


def print_report(results):
    ok = [r for r in results if r["ok"]]
    blocked = [r for r in results if not r["ok"]]
    print("\n" + "=" * 60)
    print("HUB GATE  —  %d pass, %d blocked" % (len(ok), len(blocked)))
    print("=" * 60)
    for r in results:
        mark = "PASS" if r["ok"] else "BLOCK"
        print("  [%-5s] %-40s exact=%-3d  %s"
              % (mark, r["cfg"]["slug"], r["exact"], "" if r["ok"] else "-> " + r["reason"]))
    print("=" * 60 + "\n")
    return ok, blocked
