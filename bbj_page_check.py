#!/usr/bin/env python3
"""
bbj_page_check.py  -  "Is every page up to snuff?" checker for BlackBarJobs.

WHAT IT DOES
  Opens every .html page in your site folder and checks each one against a
  short list of "what a correct page has" (and what it must NOT still have).
  Then it prints a plain report: how many are fine, and exactly which pages
  need attention and why. You hand the "needs attention" list to Claude Code.

HOW TO RUN (from your repo folder)
  python bbj_page_check.py
  python bbj_page_check.py --path "C:\\Blacbar Jobs - SIte Folder\\blackbarjobs"
  python bbj_page_check.py --csv report.csv     (also writes a spreadsheet)

No installs needed. Plain Python.
"""

import os, re, csv, argparse, sys

# ---- the markers that define a "correct" page (grounded in the live site) ----
GTM_ID              = "GTM-TP9JXK39"
SHARED_OVERLAY_JS   = "/js/bbj-register-overlay.js"
FEED_JS             = "/js/bbj-feed.js"
FEED_KEY            = "BBJ_FEED_KEY"
AUTH_SCRIPTS        = [
    "@supabase/supabase-js",
    "/js/supabase-config.js",
    "/js/bbj-auth-nav.js",
]

# things that should be GONE (leftover old systems that fire their own tracking)
LEFTOVER_PATTERNS = {
    "old sign-up modal still in page (submitAlert)"        : r"function\s+submitAlert",
    "old Gate v5 block still in page"                      : r"BBJ\s+UNIFIED\s+GATE|function\s+bbjSubmitGate",
    "old modal markup still in page"                       : r'id="modalOverlay"',
    "page fires its own conversion (should be shared)"     : r"gtag\(\s*['\"]event['\"]\s*,\s*['\"]conversion['\"]",
    "page fires its own webhook (should be shared)"        : r"hook\.us2\.make\.com",
    "old CTA to /register.html"                            : r'href="/register\.html"',
}

# the four metros, and the tokens that mean "this page is talking about that metro"
METROS = {
    "dallas":      [r"\bDFW\b", r"Dallas[\u2013\u2014-]Fort Worth", r"\bDallas\b", r"\bFort Worth\b"],
    "houston":     [r"\bHouston\b"],
    "san-antonio": [r"San Antonio"],
    "austin":      [r"\bAustin\b"],
}
# which metro a page BELONGS to is decided by its feed key / path (see detect_metro)

EMDASH = "\u2014"   # —
ENDASH = "\u2013"   # –


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def detect_metro(html, relpath):
    """Best guess at which metro this page belongs to."""
    # 1) most reliable: the feed key, e.g.  BBJ_FEED_KEY="dallas/unarmed-security-dfw"
    m = re.search(r'BBJ_FEED_KEY\s*=\s*"([^"/]+)', html)
    if m:
        seg = m.group(1).strip().lower()
        if seg in METROS:
            return seg
        if seg == "dfw":
            return "dallas"
    # 2) folder name:  /houston/...  /san-antonio/...
    parts = relpath.replace("\\", "/").lower().split("/")
    for p in parts:
        if p in METROS:
            return p
        if p == "dfw":
            return "dallas"
    # 3) filename suffix:  -dfw.html  -houston.html  -san-antonio.html  -austin.html
    low = relpath.lower()
    if low.endswith("-dfw.html") or "-dfw." in low:
        return "dallas"
    for metro in ("houston", "san-antonio", "austin"):
        if f"-{metro}." in low or low.endswith(f"-{metro}.html"):
            return metro
    return None   # unknown / not a metro page (hub, employer, register, etc.)


def has_feed_intent(html):
    """Does this page look like it is supposed to show a job feed?"""
    return any(s in html for s in (FEED_KEY, FEED_JS, "output=csv",
                                   'id="jobRows"', 'id="indexJobFeed"'))


def check_page(path, relpath):
    html = read(path)
    issues = []       # (severity, tag, message)  severity: FIX or REVIEW

    # 1) TRACKING installed
    if GTM_ID not in html:
        issues.append(("FIX", "tracking", "Missing tracking (GTM tag not found)"))

    # 2) SIGN-UP buttons open the right box
    if SHARED_OVERLAY_JS not in html:
        issues.append(("FIX", "signup", "Missing the shared sign-up script (bbj-register-overlay.js)"))
    if 'href="/register.html"' in html:
        issues.append(("FIX", "signup", "A button still points to the old /register.html"))
    # a page that has CTAs but never calls the shared opener
    if ("bbjAlertOpen(" not in html) and ("bbjAccOpen(" not in html) and ("Get Job Alerts" in html or "Browse All" in html):
        issues.append(("REVIEW", "signup", "Has sign-up buttons but none open the shared box"))

    # 3) JOB FEED on the new system (only judged if the page is meant to have one)
    if has_feed_intent(html):
        if "output=csv" in html:
            issues.append(("FIX", "feed", "Job feed is still on the OLD system (Google Sheet CSV)"))
        if FEED_KEY not in html or FEED_JS not in html:
            issues.append(("FIX", "feed", "Job feed missing the new setup (BBJ_FEED_KEY + bbj-feed.js)"))

    # 4) NO wrong-metro copy (the classic: "DFW" leaking onto a Houston/Austin/SA page)
    metro = detect_metro(html, relpath)
    if metro and metro != "dallas":
        # ignore cross-market links: a link to the Dallas hub (/dallas or /dallas/...) is allowed
        scan = re.sub(r'<a\b[^>]*href="/dallas(?:/[^"]*)?"[^>]*>.*?</a>', ' ', html, flags=re.I | re.S)
        for pat in METROS["dallas"]:
            if re.search(pat, scan):
                token = pat.replace(r"\b", "").replace("\\", "")
                issues.append(("FIX", "metro", f"Says a Dallas term ('{token}') on a {metro} page"))
                break

    # 5) NO leftover old code
    for label, pat in LEFTOVER_PATTERNS.items():
        if label == "old CTA to /register.html":
            continue  # already covered under signup
        if re.search(pat, html, re.IGNORECASE):
            issues.append(("FIX", "leftover", f"Leftover: {label}"))

    # ---- softer, house-style checks (REVIEW, not blocking) ----
    # auth scripts
    missing_auth = [s for s in AUTH_SCRIPTS if s not in html]
    if missing_auth and (SHARED_OVERLAY_JS in html):  # only nag real site pages
        issues.append(("REVIEW", "auth", f"Missing sign-in script(s): {', '.join(missing_auth)}"))

    # em-dashes (house style: none)
    n_em = html.count(EMDASH)
    if n_em:
        issues.append(("REVIEW", "copy", f"{n_em} em-dash(es) found (house style is none)"))

    # hero alt mentions the wrong metro
    hm = re.search(r'<img[^>]*class="[^"]*hero[^"]*"[^>]*alt="([^"]*)"|<img[^>]*alt="([^"]*)"[^>]*hero', html, re.IGNORECASE)
    hero_alt = None
    m2 = re.search(r'hero[^>]*<img[^>]*alt="([^"]*)"', html, re.IGNORECASE) or re.search(r'<img[^>]*src="[^"]*hero[^"]*"[^>]*alt="([^"]*)"', html, re.IGNORECASE)
    if m2:
        hero_alt = m2.group(1)
    if hero_alt and metro:
        for other, pats in METROS.items():
            if other == metro:
                continue
            if any(re.search(p, hero_alt) for p in pats):
                issues.append(("REVIEW", "hero", f"Hero image text mentions {other} on a {metro} page: \"{hero_alt}\""))
                break

    return metro, issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=".", help="Path to your site folder (default: current folder)")
    ap.add_argument("--csv", default=None, help="Optional: also write a spreadsheet report to this file")
    args = ap.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"Could not find that folder: {root}")
        sys.exit(1)

    skip_dirs = {".git", "node_modules", ".vercel", ".github"}
    pages = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            if fn.lower().endswith(".html"):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root)
                pages.append((full, rel))
    pages.sort(key=lambda x: x[1])

    clean, needs = [], []
    csv_rows = []
    for full, rel in pages:
        try:
            metro, issues = check_page(full, rel)
        except Exception as e:
            issues = [("FIX", "error", f"Could not read page: {e}")]
            metro = None
        fixes   = [i for i in issues if i[0] == "FIX"]
        reviews = [i for i in issues if i[0] == "REVIEW"]
        if not issues:
            clean.append(rel)
        else:
            needs.append((rel, fixes, reviews))
        for sev, tag, msg in (issues or []):
            csv_rows.append({"page": rel, "metro": metro or "", "severity": sev, "type": tag, "issue": msg})

    # -------- the plain report --------
    total = len(pages)
    print("=" * 64)
    print(f"BBJ PAGE CHECK   ({total} pages scanned)")
    print("=" * 64)
    print(f"\n  {len(clean)} pages: all good")
    print(f"  {len(needs)} pages: need attention\n")

    if needs:
        print("-" * 64)
        print("PAGES THAT NEED ATTENTION")
        print("-" * 64)
        for rel, fixes, reviews in needs:
            print(f"\n• {rel}")
            for sev, tag, msg in fixes:
                print(f"    [fix]    {msg}")
            for sev, tag, msg in reviews:
                print(f"    [review] {msg}")

    # a small tally by problem type, so you see the big rocks
    from collections import Counter
    tally = Counter((sev, tag) for r in csv_rows for sev, tag in [(r["severity"], r["type"])])
    if tally:
        print("\n" + "-" * 64)
        print("SUMMARY BY PROBLEM TYPE")
        print("-" * 64)
        for (sev, tag), n in sorted(tally.items(), key=lambda x: (-x[1])):
            print(f"  {n:>4}  [{sev.lower()}] {tag}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["page", "metro", "severity", "type", "issue"])
            w.writeheader()
            w.writerows(csv_rows)
        print(f"\nSpreadsheet written to: {args.csv}")

    print("\nDone.  '[fix]' = should be corrected.  '[review]' = worth a look.\n")


if __name__ == "__main__":
    main()
