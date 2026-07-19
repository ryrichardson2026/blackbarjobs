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

import argparse, json, os, re, sys

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

def bc_count(html):
    return sum(1 for m in SCRIPT_RE.finditer(html) if top_type(m.group(1)) == "BreadcrumbList")

def ld_blocks(html):
    """The exact JSON-LD <script> substrings, in order. Used to assert the existing
    schema blocks are byte-identical before and after an insert."""
    return [m.group(0) for m in SCRIPT_RE.finditer(html)]

def insert_markers(html):
    """Insert-only path (Phase 2 gap pages, which have no synthetic block to
    replace): add an EMPTY BBJ_SCHEMA marker pair immediately before </head>,
    touching nothing else. bake_page fills it with real postings later. Returns
    (new_html, note). Raises ValueError on any invariant violation."""
    if SCHEMA_START in html or SCHEMA_END in html:
        return html, "already has BBJ_SCHEMA markers"
    if any(top_type(m.group(1)) == "JobPosting" for m in SCRIPT_RE.finditer(html)):
        raise ValueError("page already has a JobPosting script; not an insert-only gap page")

    blocks_before = ld_blocks(html)
    faq_before, bc_before = faq_count(html), bc_count(html)
    i = html.find("</head>")
    if i == -1:
        raise ValueError("no </head> to anchor insertion")
    new_html = html[:i] + SCHEMA_START + SCHEMA_END + html[i:]

    # invariants: every existing JSON-LD block byte-identical; markers added once
    if ld_blocks(new_html) != blocks_before:
        raise ValueError("existing JSON-LD blocks changed during insert")
    if new_html.count(SCHEMA_START) != 1 or new_html.count(SCHEMA_END) != 1:
        raise ValueError("marker pair not inserted exactly once")
    if faq_count(new_html) != faq_before or bc_count(new_html) != bc_before:
        raise ValueError("FAQPage/BreadcrumbList count changed")
    return new_html, "inserted (FAQ %d, Breadcrumb %d unchanged)" % (faq_before, bc_before)

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

def load_gap_paths(gap_json):
    data = json.load(open(gap_json, encoding="utf-8"))
    return [r["path"] for r in data.get("gap", [])]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--insert-only", action="store_true",
                    help="Phase 2: INSERT markers into gap pages (no synthetic block "
                         "to replace). Requires --gap-json to scope the exact set.")
    ap.add_argument("--gap-json", help="audit --json output; restricts insert-only to "
                    "its gap paths so no page outside the audit is ever touched")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.insert_only and not args.gap_json:
        print("--insert-only requires --gap-json (the audited gap set).", file=sys.stderr)
        return 2

    # Scope: insert-only walks exactly the audited gap paths; replace-mode walks all.
    if args.insert_only:
        rels = load_gap_paths(args.gap_json)
        paths = [(os.path.join(args.repo, r), r) for r in rels]
    else:
        paths = []
        for root, dirs, files in os.walk(args.repo):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".vercel")]
            for f in sorted(files):
                if f.endswith(".html"):
                    full = os.path.join(root, f)
                    paths.append((full, os.path.relpath(full, args.repo).replace(os.sep, "/")))

    changed, skipped, errors = [], [], []
    for full, rel in paths:
        with open(full, encoding="utf-8", newline="") as fh:
            html = fh.read()
        try:
            new_html, note = insert_markers(html) if args.insert_only else migrate_html(html)
        except ValueError as e:
            errors.append((rel, str(e)))
            continue
        if note is None:
            continue
        if note.startswith(("migrated", "inserted")):
            changed.append(rel)
            if not args.dry_run:
                with open(full, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new_html)
        else:
            skipped.append((rel, note))

    label = "insert-only" if args.insert_only else "replace"
    print("=== bbj_schema_migrate [%s]%s ===" % (label, "  [DRY-RUN]" if args.dry_run else ""))
    print("changed:   %d" % len(changed))
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
