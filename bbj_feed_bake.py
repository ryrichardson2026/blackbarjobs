#!/usr/bin/env python3
"""
bbj_feed_bake.py  ·  Bake the job feed into static HTML (Lever 1)

Renders each in-scope page's job cards into the page HTML at snapshot time, so
the job content is present in the raw HTML on the first crawl pass and visible
to non-JS AI crawlers. js/bbj-feed.js stays on top as a live-refresh layer and
treats a baked container (data-baked="1") as non-destructive.

For each in-scope page (from bbj_page_targets.json, filtered to a market and to
files that actually exist):
  1. Read window.BBJ_FEED_KEY from the page HTML.
  2. Load feed/<KEY>.json, take data.jobs, slice(0,5) (same cap as bbj-feed.js).
  3. Detect the container: #jobRows (jf-row markup) or #indexJobFeed (hf-row).
  4. Render cards to a string BYTE-IDENTICAL to what bbj-feed.js produces
     (esc / relPosted / encodeURIComponent ported 1:1), or the same EMPTY_*
     string on an empty feed.
  5. Splice that string between <!--BBJ_BAKE_START--> / <!--BBJ_BAKE_END-->
     markers inside the container, by locating the opening tag and depth-counting
     to its matching </div>. No BeautifulSoup round-trip, so every other byte on
     the page is preserved. On a re-bake the markers are replaced in place, so
     baked cards never nest or duplicate.
  6. Add data-baked="1" to the container (live-layer non-destructive guard).

Guardrails (non-negotiable):
  #1 Zero-mojibake pre-bake assertion. If any feed value contains a mojibake
     sequence (â€", Ã, Â) the page fails loudly and nothing is written.
  #3 Count-assert. The number of card divs rendered must equal the number of
     jobs baked (min(5, feed count)); reported per page.
  #4 Marker-bounded splice (see step 5) so a re-bake replaces cleanly.
  Idempotent: re-running on an already-baked page (same feed, same bake date)
  produces zero git diff.

JobPosting JSON-LD (schema splice, same cadence as the cards):
  Emit one real JobPosting per baked card into a second marker-bounded region in
  the <head> (<!--BBJ_SCHEMA_START--> / <!--BBJ_SCHEMA_END-->). Each object's
  title/employer/location/date come from the same feed job the card is rendered
  from, so the markup mirrors the visible content 1:1 and refreshes on the same
  Tue/Thu/Sat cadence. datePosted is the feed's posted_date verbatim (never the
  bake date). A fifth guardrail count-asserts objects == rendered cards. Pages
  with no BBJ_SCHEMA markers (hubs / guides / pillars) are left untouched.
  (Still NOT bumped here: WebPage/CollectionPage dateModified, a separate pass.)

Freshness (Lever 2, only on pages that actually changed this run):
  Bump the page's <lastmod> in sitemap.xml to the bake date. Unchanged pages are
  never rewritten, so re-runs do not churn timestamps.

Usage (from the repo root):
  python bbj_feed_bake.py --repo . --market "San Antonio" --dry-run
  python bbj_feed_bake.py --repo . --market "San Antonio" \
      --pages san-antonio/jobs/military-base-security-san-antonio.html   # pilot
  python bbj_feed_bake.py --repo . --market "San Antonio"                # batch
"""

import argparse, datetime, hashlib, json, os, re, sys
from urllib.parse import quote

BASE_URL = "https://www.blackbarjobs.com"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Marker pair that bounds the baked block inside a feed container. A re-bake
# replaces only what is between these, so cards never nest or duplicate.
BAKE_START = "<!--BBJ_BAKE_START-->"
BAKE_END = "<!--BBJ_BAKE_END-->"

# Classic UTF-8-decoded-as-Latin-1 corruption sequences. None of these ever
# appear in clean English job data; a real en-dash is U+2013, not "â€".
MOJIBAKE = ("â€", "Ã", "Â")  # â€ , Ã , Â

# ---- helpers ported 1:1 from js/bbj-feed.js -------------------------------

def esc(s):
    """Mirror bbj-feed.js esc(): escape & < > " ' in that exact order."""
    s = "" if s is None else str(s)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&#39;"))

def enc(s):
    """Mirror JS encodeURIComponent(): unreserved = A-Za-z0-9 -_.!~*'()."""
    s = "" if s is None else str(s)
    # Python always leaves letters/digits/_.-~ unquoted; add !*'() to match.
    return quote(s, safe="!*'()")

def rel_posted(iso, bake_date):
    """Mirror bbj-feed.js relPosted(), relative to the bake date."""
    if not iso:
        return ""
    try:
        d = datetime.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return ""
    days = (bake_date - d).days
    if days <= 0:
        return "Posted today"
    if days == 1:
        return "Posted yesterday"
    if days < 7:
        return "Posted " + str(days) + " days ago"
    return "Posted " + MONTHS[d.month - 1] + " " + str(d.day)

# ---- card renderers (string-identical to bbj-feed.js) ---------------------

EMPTY_JR = '<div style="padding:12px;color:#999;font-size:0.85rem;">No listings right now. Check back soon.</div>'
EMPTY_HF = '<div class="hf-row"><div class="hf-body"><div class="hf-title" style="color:#5a6474;">No listings right now. Check back soon.</div></div></div>'

def render_job_rows(jobs, bake_date):
    out = []
    for j in jobs:
        url = enc(j.get("apply_link") or "")
        rp = rel_posted(j.get("posted_date"), bake_date)
        out.append(
            '<div class="jf-row" style="cursor:pointer;" onclick="bbjHandleApply(this)" data-url="' + url + '">'
            '<div class="jf-body">'
            '<div class="jf-title">' + esc(j.get("title")) + '</div>'
            '<div class="jf-meta"><span class="jf-company">' + esc(j.get("company")) + '</span>'
            + (('<span class="jf-sep">&middot;</span><span class="jf-loc">' + esc(j.get("location")) + '</span>') if j.get("location") else '')
            + (('<span class="jf-pay">' + esc(j.get("pay")) + '</span>') if j.get("pay") else '')
            + (('<span class="jf-sep">&middot;</span><span class="jf-date" style="color:#1a6b2e;font-weight:600;">' + esc(rp) + '</span>') if rp else '')
            + '</div></div><a class="jf-apply">View</a></div>'
        )
    return "".join(out)

def render_index_feed(jobs, bake_date):
    out = []
    for j in jobs:
        url = enc(j.get("apply_link") or "")
        rp = rel_posted(j.get("posted_date"), bake_date)
        out.append(
            '<div class="hf-row" style="display:flex;align-items:center;justify-content:space-between;cursor:pointer;" onclick="handleIndexApply(\'' + url + '\')">'
            '<div class="hf-body">'
            '<div class="hf-title">' + esc(j.get("title")) + '</div>'
            '<div class="hf-meta">' + esc(j.get("company")) + ' &nbsp;&middot;&nbsp; ' + esc(j.get("location"))
            + ((' &nbsp;&middot;&nbsp; <span style="color:#1a6b2e;font-weight:600;">' + esc(rp) + '</span>') if rp else '') + '</div>'
            '</div>'
            '<div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">'
            '<span style="font-size:0.6rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;background:#1a6b2e;color:#fff;padding:2px 7px;border-radius:3px;">New</span>'
            '<span style="padding:6px 12px;background:#FFC300;color:#000814;font-family:\'Barlow Condensed\',sans-serif;font-size:0.8rem;font-weight:800;letter-spacing:0.05em;text-transform:uppercase;border-radius:8px;pointer-events:none;">View</span>'
            '</div></div>'
        )
    return "".join(out)

ROW_CLASS = {"jobRows": "jf-row", "indexJobFeed": "hf-row"}

# ---- container splice (byte-preserving) -----------------------------------

KEY_RE = re.compile(r'BBJ_FEED_KEY\s*=\s*"([^"]+)"')

class BakeError(Exception):
    pass

def assert_no_mojibake(jobs, feed_key):
    """Guardrail #1: refuse to bake if any feed value carries UTF-8 mojibake."""
    for j in jobs:
        for fld in ("title", "company", "location", "pay", "apply_link"):
            v = j.get(fld)
            if not v:
                continue
            v = str(v)
            for seq in MOJIBAKE:
                if seq in v:
                    raise BakeError(
                        "mojibake in feed %s field %s: %r" % (feed_key, fld, v))

def find_container(html, cid):
    """Return (open_start, open_end_inclusive, inner_start, inner_end) for the
    element whose id == cid, matching the opening <div ...> to its balanced
    </div> by depth counting. inner = html[inner_start:inner_end]."""
    marker = 'id="' + cid + '"'
    n = html.count(marker)
    if n == 0:
        return None
    if n > 1:
        raise BakeError('container id="%s" appears %d times' % (cid, n))
    mpos = html.index(marker)
    open_start = html.rfind("<", 0, mpos)
    if open_start == -1:
        raise BakeError('no opening "<" before id="%s"' % cid)
    open_end = html.index(">", mpos)          # end of the opening tag
    inner_start = open_end + 1
    # depth-count divs from just after the opening tag
    depth = 1
    tok = re.compile(r'<div\b|</div\s*>', re.I)
    pos = inner_start
    while depth > 0:
        m = tok.search(html, pos)
        if not m:
            raise BakeError('unbalanced <div> under id="%s"' % cid)
        if m.group(0).lower().startswith("</"):
            depth -= 1
            if depth == 0:
                return (open_start, open_end, inner_start, m.start())
        else:
            depth += 1
        pos = m.end()
    raise BakeError('unreachable')  # pragma: no cover

def ensure_baked_attr(open_tag):
    """Add data-baked="1" to the opening tag once; idempotent."""
    if "data-baked" in open_tag:
        return open_tag
    assert open_tag.endswith(">")
    self_close = open_tag.endswith("/>")
    core = open_tag[:-2] if self_close else open_tag[:-1]
    return core.rstrip() + ' data-baked="1"' + ("/>" if self_close else ">")

def splice_container(html, loc, cards):
    """Guardrail #4: place BAKE_START..cards..BAKE_END inside the container.
    On the first bake the whole inner (empty or skeleton) is replaced with the
    marker block; on a re-bake only the region between existing markers is
    swapped, so nothing nests or duplicates."""
    open_start, open_end, inner_start, inner_end = loc
    inner = html[inner_start:inner_end]
    block = BAKE_START + cards + BAKE_END
    si = inner.find(BAKE_START)
    ei = inner.find(BAKE_END)
    if si != -1 and ei != -1 and ei > si:
        new_inner = inner[:si] + block + inner[ei + len(BAKE_END):]
    elif si != -1 or ei != -1:
        raise BakeError("unbalanced BBJ_BAKE markers in container")
    else:
        new_inner = block
    open_tag = html[open_start:open_end + 1]
    new_open = ensure_baked_attr(open_tag)
    return html[:open_start] + new_open + new_inner + html[inner_end:]

# ---- JobPosting schema (Google for Jobs) ----------------------------------
# One real JobPosting per baked card, spliced between BBJ_SCHEMA markers in the
# <head> so the JSON-LD refreshes on the SAME cron cadence as the cards. The old
# path emitted one synthetic per-page posting at generation time that never
# refreshed and named BlackBarJobs (not the employer) as hiringOrganization.
# Rules baked in here (non-negotiable, see the schema brief):
#   - Markup mirrors visible content 1:1. One object per rendered card, and the
#     count-assert below fails the bake if they ever diverge. Zero cards -> zero
#     objects and no empty array (render_job_schema returns "").
#   - datePosted comes from the feed's posted_date and nothing else. Never the
#     bake date / today(); a stale feed date stays stale (dropped upstream).
#   - Only feed-present fields are emitted. streetAddress / postalCode /
#     baseSalary are never synthesized; a "missing recommended field" warning is
#     acceptable, a fabricated value is not.
#   - directApply is always false: BBJ outlinks to the employer's apply_link.

SCHEMA_START = "<!--BBJ_SCHEMA_START-->"
SCHEMA_END = "<!--BBJ_SCHEMA_END-->"

# schedule -> Google employmentType. Emitted ONLY on an exact match; anything
# else (None, "Per diem", etc.) omits the field rather than guessing.
EMPLOYMENT_TYPE = {
    "Full-time": "FULL_TIME",
    "Part-time": "PART_TIME",
    "Contractor": "CONTRACTOR",
    "Temp work": "TEMPORARY",
    "Internship": "INTERN",
}

def job_identifier(company, title, location):
    """Stable per-job id, byte-identical to bbj_feed_fetch.job_hash (company|title|
    location, lowercased/space-collapsed, sha1[:12]). Reusing the dedupe hash gives
    Google one identity for the same job across metro pages."""
    basis = "|".join(re.sub(r"\s+", " ", (x or "").strip().lower())
                     for x in (company, title, location))
    return hashlib.sha1(basis.encode()).hexdigest()[:12]

def split_location(loc):
    """'Houston, TX' -> ('Houston', 'TX'). Region omitted (None) when absent."""
    if not loc:
        return None, None
    parts = [p.strip() for p in str(loc).split(",")]
    if len(parts) >= 2:
        return (parts[0] or None), (parts[1] or None)
    return (parts[0] or None), None

def job_description(j):
    """A plain-language description restating the job's own visible card fields
    (title, company, location, schedule). Google requires JobPosting.description,
    so it can never be empty. This is not synthesized data: it mirrors exactly what
    the rendered card shows (guardrail: markup mirrors visible content)."""
    bits = [((j.get("title") or "Security officer position").strip().rstrip(".")) + "."]
    if j.get("company"):
        bits.append("Hiring company: " + str(j["company"]).strip() + ".")
    if j.get("location"):
        bits.append("Location: " + str(j["location"]).strip() + ".")
    if j.get("schedule"):
        bits.append("Schedule: " + str(j["schedule"]).strip() + ".")
    bits.append("See full details and apply on the employer site.")
    return " ".join(bits)

def plus_days(iso, n):
    """ISO date + n days, or None if the input is not a parseable date."""
    try:
        d = datetime.date.fromisoformat(str(iso)[:10])
    except (ValueError, TypeError):
        return None
    return (d + datetime.timedelta(days=n)).isoformat()

def build_job_posting(j):
    """One JobPosting object from one feed job. Only feed-present fields are
    emitted; nothing is invented."""
    title = ((j.get("title") or "").strip()) or None
    company = ((j.get("company") or "").strip()) or None
    location = j.get("location")
    locality, region = split_location(location)
    obj = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": title,
        "description": job_description(j),
        "identifier": {"@type": "PropertyValue",
                       "name": company or "BlackBarJobs",
                       "value": job_identifier(company, title, location)},
        "hiringOrganization": {"@type": "Organization", "name": company},
        "jobLocation": {"@type": "Place", "address": {
            "@type": "PostalAddress",
            "addressLocality": locality,
            "addressRegion": region,
            "addressCountry": "US"}},
        "directApply": False,
        "url": j.get("apply_link") or None,
    }
    posted = j.get("posted_date")
    if posted:                                          # never re-stamped
        obj["datePosted"] = str(posted)[:10]
        vt = plus_days(posted, 60)                      # validThrough = posted + 60d
        if vt:
            obj["validThrough"] = vt
    et = EMPLOYMENT_TYPE.get((j.get("schedule") or "").strip())
    if et:
        obj["employmentType"] = et
    return obj

def render_job_schema(jobs):
    """Return the <script> string for the JobPosting array, or '' when there are no
    jobs (zero cards -> zero objects, no empty array)."""
    if not jobs:
        return ""
    arr = [build_job_posting(j) for j in jobs]
    payload = json.dumps(arr, ensure_ascii=False, separators=(",", ":"))
    return '<script type="application/ld+json">' + payload + '</script>'

def splice_schema(html, jobs):
    """Replace the region between BBJ_SCHEMA markers with a JobPosting array whose
    object count equals the rendered-card count. Pages with no markers (hub / guide /
    pillar pages that carry ItemList / Article and must never carry JobPosting) are
    left untouched. Marker-bounded and idempotent, mirroring splice_container."""
    si = html.find(SCHEMA_START)
    ei = html.find(SCHEMA_END)
    if si == -1 and ei == -1:
        return html                                     # no schema region on this page
    if si == -1 or ei == -1 or ei < si:
        raise BakeError("unbalanced BBJ_SCHEMA markers")
    script = render_job_schema(jobs)
    n_obj = script.count('"@type":"JobPosting"')        # compact dumps -> exact token
    if n_obj != len(jobs):                              # guardrail #5: 1 object / card
        raise BakeError("schema object count %d != cards baked %d" % (n_obj, len(jobs)))
    inner_start = si + len(SCHEMA_START)
    return html[:inner_start] + script + html[ei:]

def bake_page(html, feed_key, feed_dir, bake_date):
    """Return (new_html, changed, note). Raises BakeError on structural trouble."""
    for cid, renderer, empty in (
        ("jobRows", render_job_rows, EMPTY_JR),
        ("indexJobFeed", render_index_feed, EMPTY_HF),
    ):
        loc = find_container(html, cid)
        if loc:
            break
    else:
        raise BakeError("no #jobRows or #indexJobFeed container found")

    feed_path = os.path.join(feed_dir, feed_key + ".json")
    if not os.path.exists(feed_path):
        raise BakeError("feed file missing: " + feed_path)
    with open(feed_path, encoding="utf-8") as fh:
        data = json.load(fh)
    all_jobs = data.get("jobs") or []
    assert_no_mojibake(all_jobs, feed_key)              # guardrail #1
    jobs = all_jobs[:5]                                 # same cap as bbj-feed.js
    cards = renderer(jobs, bake_date) if jobs else empty

    if jobs:                                            # guardrail #3
        n_rendered = cards.count('class="' + ROW_CLASS[cid] + '"')
        if n_rendered != len(jobs):
            raise BakeError("render count %d != jobs baked %d"
                            % (n_rendered, len(jobs)))

    new_html = splice_container(html, loc, cards)
    new_html = splice_schema(new_html, jobs)            # JobPosting JSON-LD, if markers
    changed = new_html != html
    note = ("%d/%d jobs" % (len(jobs), len(all_jobs))) if jobs else "EMPTY"
    return new_html, changed, note

# ---- sitemap lastmod bump -------------------------------------------------

def enumerate_walk(repo, walk_dir):
    """Enumerate bakeable *.html under walk_dir: a page qualifies if it carries a
    BBJ_FEED_KEY and a #jobRows or #indexJobFeed container. Returns (scope, skipped)
    where scope is a list of {"path": rel} and skipped lists pages intentionally not
    baked (pillar/guide/apply pages with no feed). Source of truth is the page
    itself, so a stale manifest cannot cause pages to be silently missed."""
    base = os.path.join(repo, walk_dir)
    scope, skipped = [], []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".vercel")]
        for f in sorted(files):
            if not f.endswith(".html"):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, repo).replace(os.sep, "/")
            with open(full, encoding="utf-8", newline="") as fh:
                html = fh.read()
            if not KEY_RE.search(html):
                skipped.append(rel + "  (no BBJ_FEED_KEY)")
                continue
            if 'id="jobRows"' not in html and 'id="indexJobFeed"' not in html:
                skipped.append(rel + "  (no feed container)")
                continue
            scope.append({"path": rel})
    scope.sort(key=lambda t: t["path"])
    return scope, skipped

def page_to_loc(path):
    """Map a repo-relative page path to its sitemap <loc> URL."""
    url = path.replace(os.sep, "/")
    if url.endswith(".html"):
        url = url[:-5]
    if url.endswith("/index"):
        url = url[:-len("/index")]
    if url == "index":
        url = ""
    return BASE_URL + "/" + url if url else BASE_URL

def bump_sitemap(sitemap_path, changed_paths, bake_iso):
    """Set <lastmod> to bake_iso for the <url> blocks whose <loc> matches a
    changed page. Returns (bumped, missing_locs)."""
    with open(sitemap_path, encoding="utf-8", newline="") as fh:
        sm = fh.read()
    locs = {page_to_loc(p) for p in changed_paths}
    bumped, seen = 0, set()
    block_re = re.compile(r"(<url>\s*<loc>)(.*?)(</loc>\s*<lastmod>)(.*?)(</lastmod>)",
                          re.S)

    def repl(m):
        nonlocal bumped
        loc = m.group(2).strip()
        if loc in locs:
            seen.add(loc)
            if m.group(4).strip() != bake_iso:
                bumped += 1
                return m.group(1) + m.group(2) + m.group(3) + bake_iso + m.group(5)
        return m.group(0)

    new_sm = block_re.sub(repl, sm)
    missing = sorted(locs - seen)
    if new_sm != sm:
        with open(sitemap_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(new_sm)
    return bumped, missing

# ---- driver ---------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="BBJ static feed baker")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--targets", default="bbj_page_targets.json")
    ap.add_argument("--market", required=True)
    ap.add_argument("--pages", nargs="*", help="restrict to these repo-relative paths")
    ap.add_argument("--walk-dir", help="bake every *.html under this dir using each "
                    "page's own embedded BBJ_FEED_KEY, bypassing the manifest. For "
                    "markets whose manifest is stale (e.g. DFW after the restructure).")
    ap.add_argument("--date", help="bake date YYYY-MM-DD (default: today)")
    ap.add_argument("--sitemap", default="sitemap.xml")
    ap.add_argument("--no-sitemap", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    bake_date = (datetime.date.fromisoformat(args.date) if args.date
                 else datetime.date.today())
    bake_iso = bake_date.isoformat()
    repo = args.repo
    feed_dir = os.path.join(repo, "feed")

    if args.walk_dir:
        scope, skipped = enumerate_walk(repo, args.walk_dir)
        print("=== bbj_feed_bake  market=%s  date=%s  [WALK-DIR %s]%s ===" %
              (args.market, bake_iso, args.walk_dir,
               "  [DRY-RUN]" if args.dry_run else ""))
        print("bakeable pages found:   %d" % len(scope))
        print("skipped (no key/container, NOT baked): %d" % len(skipped))
        for p in skipped:
            print("   - %s" % p)
    else:
        targets = json.load(open(os.path.join(repo, args.targets), encoding="utf-8"))["targets"]
        market = [t for t in targets if t["market"].lower() == args.market.lower()]

        # split real vs phantom (target path with no file on disk)
        real, phantom = [], []
        for t in market:
            (real if os.path.exists(os.path.join(repo, t["path"])) else phantom).append(t)

        if args.pages:
            want = {p.replace("\\", "/") for p in args.pages}
            scope = [t for t in real if t["path"].replace("\\", "/") in want]
        else:
            scope = real

        print("=== bbj_feed_bake  market=%s  date=%s%s ===" %
              (args.market, bake_iso, "  [DRY-RUN]" if args.dry_run else ""))
        print("targets in market:      %d" % len(market))
        print("real (file exists):     %d" % len(real))
        print("in scope this run:      %d" % len(scope))
        if phantom:
            print("PHANTOM targets (no file on disk, NOT touched, flag for manifest cleanup):")
            for t in phantom:
                print("   - %s" % t["path"])

    changed_paths, errors, baked = [], [], 0
    for t in scope:
        path = t["path"]
        full = os.path.join(repo, path)
        with open(full, encoding="utf-8", newline="") as fh:
            html = fh.read()
        m = KEY_RE.search(html)
        if not m:
            errors.append((path, "no BBJ_FEED_KEY"))
            continue
        key = m.group(1)
        try:
            new_html, changed, note = bake_page(html, key, feed_dir, bake_date)
        except BakeError as e:
            errors.append((path, str(e)))
            continue
        baked += 1
        flag = "CHANGED" if changed else "same"
        print("  [%-7s] %-58s %s (%s)" % (flag, path, note, key))
        if changed:
            changed_paths.append(path)
            if not args.dry_run:
                with open(full, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new_html)

    print("--- summary ---")
    print("processed:              %d" % baked)
    print("changed:                %d" % len(changed_paths))
    if errors:
        print("ERRORS (%d):" % len(errors))
        for p, e in errors:
            print("   ! %s -> %s" % (p, e))

    if changed_paths and not args.no_sitemap:
        sm_path = os.path.join(repo, args.sitemap)
        if args.dry_run:
            print("sitemap: would bump lastmod->%s for %d changed pages" %
                  (bake_iso, len(changed_paths)))
        else:
            bumped, missing = bump_sitemap(sm_path, changed_paths, bake_iso)
            print("sitemap: bumped %d <lastmod> to %s" % (bumped, bake_iso))
            for loc in missing:
                print("   ! sitemap loc not found for changed page: %s" % loc)

    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
