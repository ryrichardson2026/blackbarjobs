#!/usr/bin/env python3
"""
bbj_feed_patch.py  ·  Phase 5 of the BBJ Supabase feed

Rewires each feed page from the Google Sheet CSV to the static JSON snapshot.
For every page in bbj_page_targets.json it finds the inline feed <script> block
(the one containing "output=csv", which is unique to that block) and replaces
the whole block with two small tags:

    <script>window.BBJ_FEED_KEY="<page key>";</script>
    <script src="/js/bbj-feed.js" defer></script>

Nothing else on the page is touched. The shared /js/bbj-feed.js then renders the
page's feed from /feed/<page key>.json. Idempotent: a page already patched has no
"output=csv" block, so it is skipped on a re-run.

ALWAYS run --dry-run first, and run this on a branch with a Vercel preview before
merging. Backups (.bak) are written next to each file unless --no-backup.

Usage (from the repo root):
  python bbj_feed_patch.py --repo . --dry-run
  python bbj_feed_patch.py --repo . --market "San Antonio"   # patch one metro first
  python bbj_feed_patch.py --repo .                          # patch all
  python bbj_feed_patch.py --repo . --restore                # undo from .bak files
"""

import argparse, json, os, re, sys

SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>.*?</script>", re.I | re.S)

def find_feed_block(html):
    for m in SCRIPT_BLOCK.finditer(html):
        if "output=csv" in m.group(0):
            return m.span()
    return None

def replacement(key):
    return ('<script>window.BBJ_FEED_KEY=' + json.dumps(key) + ';</script>\n'
            '<script src="/js/bbj-feed.js" defer></script>')

def main():
    ap = argparse.ArgumentParser(description="BBJ Phase 5 page patcher")
    ap.add_argument("--repo", default=".", help="repo root (contains dallas/, houston/, ...)")
    ap.add_argument("--targets", default="bbj_page_targets.json")
    ap.add_argument("--market", help="patch only one metro")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--restore", action="store_true", help="restore every .bak next to a target")
    args = ap.parse_args()

    targets = json.load(open(args.targets, encoding="utf-8"))["targets"]
    if args.market:
        targets = [t for t in targets if t["market"].lower() == args.market.lower()]

    if args.restore:
        n = 0
        for t in targets:
            p = os.path.join(args.repo, t["path"]); bak = p + ".bak"
            if os.path.exists(bak):
                os.replace(bak, p); n += 1
        print(f"Restored {n} files from .bak"); return

    patched, skipped, missing, nokey = 0, [], [], []
    for t in targets:
        p = os.path.join(args.repo, t["path"])
        if not os.path.exists(p):
            missing.append(t["path"]); continue
        html = open(p, encoding="utf-8").read()
        span = find_feed_block(html)
        if not span:
            skipped.append(t["path"]); continue   # already patched or no CSV block
        new_html = html[:span[0]] + replacement(t["key"]) + html[span[1]:]
        if args.dry_run:
            patched += 1; continue
        if not args.no_backup:
            open(p + ".bak", "w", encoding="utf-8").write(html)
        open(p, "w", encoding="utf-8").write(new_html)
        patched += 1

    verb = "would patch" if args.dry_run else "patched"
    print(f"{verb}: {patched}")
    print(f"skipped (no CSV block / already done): {len(skipped)}")
    if missing:
        print(f"missing files: {len(missing)}  e.g. {missing[:3]}")
    if skipped and args.dry_run:
        print("  first skipped:", ", ".join(skipped[:5]))


if __name__ == "__main__":
    main()
