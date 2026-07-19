#!/usr/bin/env python3
"""
bbj_schema_migrate.py  ·  One-time: synthetic JobPosting -> BBJ_SCHEMA markers

The old generator emitted one synthetic per-page JobPosting <script> in the
<head> (frozen datePosted, hiringOrganization = BlackBarJobs). bbj_feed_bake.py
now fills a marker-bounded region with one REAL JobPosting per baked card. This
migration bridges the 147 existing pages: it removes the synthetic script and
drops an EMPTY <!--BBJ_SCHEMA_START-->/<!--BBJ_SCHEMA_END--> pair in its exact
place. The next bake run per market fills the markers with real postings.

Discipline (matches the schema brief):
  - Read before write; per file, count-assert exactly ONE JobPosting script is
    removed and the FAQPage count is unchanged, or the file is left untouched and
    reported. Every other byte is preserved (only the matched <script> substring
    is swapped for the marker pair).
  - ItemList / CollectionPage / FAQPage / BreadcrumbList are never touched: only a
    script whose top-level @type is exactly "JobPosting" is matched, and hub pages
    carry CollectionPage (not JobPosting), so they are skipped by construction.

Usage (from repo root):
  python automation/bbj_schema_migrate.py --dry-run
  python automation/bbj_schema_migrate.py
"""

import argparse, os, re, sys

SCHEMA_START = "<!--BBJ_SCHEMA_START-->"
SCHEMA_END = "<!--BBJ_SCHEMA_END-->"

SCRIPT_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
TYPE_RE = re.compile(r'"@type"\s*:\s*"([^"]+)"')

def top_type(body):
    """Top-level @type of a JSON-LD body (first @type wins; nested @types follow)."""
    m = TYPE_RE.search(body)
    return m.group(1) if m else None

def faq_count(html):
    return sum(1 for m in SCRIPT_RE.finditer(html) if top_type(m.group(1)) == "FAQPage")

def migrate_html(html):
    """Return (new_html, note). note is None when nothing changed.
    Raises ValueError on any invariant violation (caller reports and skips)."""
    if SCHEMA_START in html or SCHEMA_END in html:
        return html, "already has BBJ_SCHEMA markers"

    jp = [m for m in SCRIPT_RE.finditer(html) if top_type(m.group(1)) == "JobPosting"]
    if not jp:
        return html, None                                   # no synthetic block (hub/other)
    if len(jp) != 1:
        raise ValueError("expected 1 JobPosting script, found %d" % len(jp))

    faq_before = faq_count(html)
    m = jp[0]
    new_html = html[:m.start()] + SCHEMA_START + SCHEMA_END + html[m.end():]

    # invariants: exactly one JobPosting removed, markers present once, FAQ unchanged
    if SCRIPT_RE.search(new_html) and any(
            top_type(x.group(1)) == "JobPosting" for x in SCRIPT_RE.finditer(new_html)):
        raise ValueError("a JobPosting script survived the swap")
    if new_html.count(SCHEMA_START) != 1 or new_html.count(SCHEMA_END) != 1:
        raise ValueError("marker pair not inserted exactly once")
    if faq_count(new_html) != faq_before:
        raise ValueError("FAQPage count changed %d -> %d" % (faq_before, faq_count(new_html)))
    return new_html, "migrated (FAQ %d unchanged)" % faq_before

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changed, skipped, errors = [], [], []
    for root, dirs, files in os.walk(args.repo):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".vercel")]
        for f in sorted(files):
            if not f.endswith(".html"):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, args.repo).replace(os.sep, "/")
            with open(full, encoding="utf-8", newline="") as fh:
                html = fh.read()
            try:
                new_html, note = migrate_html(html)
            except ValueError as e:
                errors.append((rel, str(e)))
                continue
            if note is None:
                continue
            if note.startswith("migrated"):
                changed.append(rel)
                if not args.dry_run:
                    with open(full, "w", encoding="utf-8", newline="") as fh:
                        fh.write(new_html)
            else:
                skipped.append((rel, note))

    print("=== bbj_schema_migrate%s ===" % ("  [DRY-RUN]" if args.dry_run else ""))
    print("migrated:  %d" % len(changed))
    for r in changed:
        print("   + %s" % r)
    if skipped:
        print("skipped (already migrated): %d" % len(skipped))
        for r, n in skipped:
            print("   . %s  (%s)" % (r, n))
    if errors:
        print("ERRORS: %d" % len(errors))
        for r, e in errors:
            print("   ! %s -> %s" % (r, e))
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
