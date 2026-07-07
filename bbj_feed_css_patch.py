#!/usr/bin/env python3
"""
bbj_feed_css_patch.py  ·  add the missing job-feed CSS to pages that lack it

A handful of pages render the job list with jf-row markup but never define the
.jf-row styles, so the listings show as unstyled text. This injects the same
.jf- CSS block the other ~176 pages already use, right before the page's first
</style>. It only touches pages that (a) use id="jobRows" and (b) do not already
define .jf-row, so it is safe and idempotent.

Run from the repo root:
  python bbj_feed_css_patch.py --repo . --dry-run
  python bbj_feed_css_patch.py --repo . --no-backup
"""
import argparse, os, re

CSS = """
/* job feed rows */
.jf-row { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--border); cursor: pointer; }
.jf-row:last-child { border-bottom: none; }
.jf-body { flex: 1; min-width: 0; }
.jf-title { font-family: 'Barlow Condensed', sans-serif; font-size: 0.95rem; font-weight: 800; color: var(--navy-deep); line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.jf-meta { display: flex; align-items: center; gap: 0; margin-top: 2px; font-size: 0.7rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.jf-company { font-weight: 600; color: var(--charcoal); }
.jf-loc { color: var(--muted); }
.jf-sep { margin: 0 5px; color: #d0d5dd; }
.jf-pay { font-size: 0.65rem; font-weight: 700; color: #1a6b2e; background: #e6f4eb; padding: 1px 5px; border-radius: 3px; margin-left: 6px; flex-shrink: 0; }
.jf-apply { flex-shrink: 0; padding: 6px 12px; background: var(--navy-deep); color: var(--gold); font-family: 'Barlow Condensed', sans-serif; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase; border-radius: 4px; text-decoration: none; transition: background 0.12s; }
.jf-apply:hover { background: var(--navy-light); }
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changed, skipped = [], 0
    for root, _, files in os.walk(args.repo):
        if ".git" in root: continue
        for fn in files:
            if not fn.endswith(".html"): continue
            p = os.path.join(root, fn)
            html = open(p, encoding="utf-8", errors="ignore").read()
            if 'id="jobRows"' not in html or ".jf-row" in html:
                continue
            idx = html.find("</style>")
            if idx == -1:
                skipped += 1; continue
            new = html[:idx] + CSS + html[idx:]
            rel = os.path.relpath(p, args.repo)
            if args.dry_run:
                changed.append(rel); continue
            if not args.no_backup:
                open(p + ".bak", "w", encoding="utf-8").write(html)
            open(p, "w", encoding="utf-8").write(new)
            changed.append(rel)

    verb = "would fix" if args.dry_run else "fixed"
    print(f"{verb}: {len(changed)} pages")
    for c in changed: print("  " + c)
    if skipped: print(f"skipped (no </style>): {skipped}")

if __name__ == "__main__":
    main()
