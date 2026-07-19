#!/usr/bin/env python3
"""
bbj_schema_fill.py  ·  One-time: fill empty BBJ_SCHEMA markers with real postings

After bbj_schema_migrate.py drops empty <!--BBJ_SCHEMA_START-->/<!--BBJ_SCHEMA_END-->
pairs, this walks a market dir, and for EVERY page that actually carries those
markers (source of truth = the page itself, not the stale manifest), runs
bbj_feed_bake.bake_page to fill them with one real JobPosting per baked card.

Scoped on purpose: it touches only marker-bearing pages, so it never re-bakes the
hub / geo / suburb pages under the same market dir that have a feed but no
JobPosting markers (those keep to the normal Tue/Thu/Sat cron). bake_page still
refreshes the job cards on the pages it does touch (same atomic pass), which is
the intended feed behavior. Changed pages get their sitemap <lastmod> bumped so
the recrawl picks up the new schema.

Usage (from repo root):
  python automation/bbj_schema_fill.py --dir houston --market Houston --dry-run
  python automation/bbj_schema_fill.py --dir houston --market Houston
"""

import argparse, datetime, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bbj_feed_bake import bake_page, bump_sitemap, BakeError, KEY_RE, SCHEMA_START

def find_marker_pages(base):
    out = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".vercel")]
        for f in sorted(files):
            if not f.endswith(".html"):
                continue
            full = os.path.join(root, f)
            with open(full, encoding="utf-8", newline="") as fh:
                html = fh.read()
            if SCHEMA_START in html:
                out.append(full)
    out.sort()
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--dir", required=True, help="market dir to walk, e.g. houston")
    ap.add_argument("--market", required=True, help="label for reporting only")
    ap.add_argument("--date", help="bake date YYYY-MM-DD (default: today)")
    ap.add_argument("--sitemap", default="sitemap.xml")
    ap.add_argument("--no-sitemap", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    bake_date = (datetime.date.fromisoformat(args.date) if args.date
                 else datetime.date.today())
    repo = args.repo
    feed_dir = os.path.join(repo, "feed")
    base = os.path.join(repo, args.dir)

    pages = find_marker_pages(base)
    print("=== bbj_schema_fill  market=%s  dir=%s  date=%s%s ===" %
          (args.market, args.dir, bake_date.isoformat(),
           "  [DRY-RUN]" if args.dry_run else ""))
    print("marker pages found:     %d" % len(pages))

    changed_paths, errors, filled = [], [], 0
    for full in pages:
        rel = os.path.relpath(full, repo).replace(os.sep, "/")
        with open(full, encoding="utf-8", newline="") as fh:
            html = fh.read()
        m = KEY_RE.search(html)
        if not m:
            errors.append((rel, "no BBJ_FEED_KEY"))
            continue
        key = m.group(1)
        try:
            new_html, changed, note = bake_page(html, key, feed_dir, bake_date)
        except BakeError as e:
            errors.append((rel, str(e)))
            continue
        filled += 1
        print("  [%-7s] %-58s %s" % ("CHANGED" if changed else "same", rel, note))
        if changed:
            changed_paths.append(rel)
            if not args.dry_run:
                with open(full, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new_html)

    print("--- summary ---")
    print("processed:              %d" % filled)
    print("changed:                %d" % len(changed_paths))
    if errors:
        print("ERRORS (%d):" % len(errors))
        for r, e in errors:
            print("   ! %s -> %s" % (r, e))

    if changed_paths and not args.no_sitemap and not args.dry_run:
        bumped, missing = bump_sitemap(os.path.join(repo, args.sitemap),
                                       changed_paths, bake_date.isoformat())
        print("sitemap: bumped %d <lastmod> to %s" % (bumped, bake_date.isoformat()))
        for loc in missing:
            print("   ! sitemap loc not found for changed page: %s" % loc)

    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
