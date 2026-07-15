#!/usr/bin/env python3
"""
bbj_link_audit.py  -  Full internal-link audit for BlackBarJobs.

Cross-checks THREE sources of truth against each other:
  1. The real pages that actually exist on disk (the repo files).
  2. Every internal link written on those pages (<a href>).
  3. The sitemap(s).

And reports every place they disagree:
  A) BROKEN LINKS      - a page links to an internal URL that has no real file (the 404 cause).
  B) DEAD SITEMAP URLS - the sitemap lists a URL that has no real file (tells Google to crawl a 404).
  C) MISSING FROM MAP  - a real page the sitemap never lists (Google may never find it).
  D) ORPHAN PAGES      - a real page that no other page links to (users/crawlers can't reach it).

For broken links it AUTO-SUGGESTS the correct target by matching slug words, so
`houston-armed-security` -> `armed-security-houston` is found for you. That suggestion list IS
your redirect/fix map.

RUN (from repo root):  python bbj_link_audit.py
       or:            python bbj_link_audit.py --path "C:\\Blacbar Jobs - SIte Folder\\blackbarjobs" --csv audit.csv
No installs needed.
"""

import os, re, csv, json, argparse, sys, datetime
from difflib import get_close_matches
from collections import defaultdict

DOMAIN = "blackbarjobs.com"
SKIP_DIRS = {".git", "node_modules", ".vercel", ".github"}

# ---- health-audit constants (Check A schema, Check B freshness, --ci mode) ----
STALENESS_DAYS   = 14   # a feed's newest job must be within this many days (matches feed_fetch --staleness-days)
MAX_BAKE_LAG_DAYS = 3   # baked HTML card dates may trail the feed by at most one refresh cycle (Tue/Thu/Sat gap)
JOBPOSTING_REQUIRED = ("title", "description", "hiringOrganization", "jobLocation", "datePosted")
BAKE_START = "<!--BBJ_BAKE_START-->"
BAKE_END   = "<!--BBJ_BAKE_END-->"
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
LDJSON_RE   = re.compile(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
FEED_KEY_RE = re.compile(r'BBJ_FEED_KEY\s*=\s*"([^"]+)"')
POSTED_TEXT_RE = re.compile(r'Posted (?:today|yesterday|\d+ days? ago|[A-Z][a-z]{2} \d{1,2})')

# ---------------- file / url helpers ----------------

def gather_files(root):
    files = set()
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), root).replace("\\", "/")
            files.add(rel)
    return files

def file_to_url(rel):
    """repo file path -> the clean URL it serves at."""
    u = "/" + rel
    if u.endswith("/index.html"):
        u = u[:-len("index.html")].rstrip("/") or "/"
    elif u.endswith(".html"):
        u = u[:-len(".html")]
    return u

def norm_path(p):
    """strip domain/scheme/query/anchor, return a leading-slash path."""
    p = p.strip()
    p = re.sub(r"^https?://", "", p)                     # drop scheme
    low = p.lower()
    if low.startswith("www." + DOMAIN) or low.startswith(DOMAIN):   # drop our host (with or without www.)
        p = "/" + p.split("/", 1)[1] if "/" in p else "/"
    p = p.split("#")[0].split("?")[0]
    if not p.startswith("/"):
        return None            # relative or scheme-y; resolved by caller
    return p

def resolve(path, files):
    """Given a URL path, return the repo file that serves it, or None (clean-URL aware)."""
    if path in ("/", ""):
        return "index.html" if "index.html" in files else None
    p = path.strip("/")
    for cand in (p, p + ".html", p + "/index.html"):
        if cand in files:
            return cand
    return None

def slug_tokens(url_or_path):
    last = url_or_path.rstrip("/").split("/")[-1]
    last = re.sub(r"\.html$", "", last)
    return frozenset(t for t in re.split(r"[-_]", last) if t)

# ---------------- link extraction ----------------

HREF = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.I)

def links_on_page(root, rel):
    try:
        with open(os.path.join(root, rel), "r", encoding="utf-8", errors="replace") as fh:
            html = fh.read()
    except Exception:
        return []
    return HREF.findall(html)

def is_internal(href):
    h = href.strip().lower()
    if h.startswith(("mailto:", "tel:", "javascript:", "#", "data:")):
        return False
    if h.startswith("//"):
        return False
    if h.startswith(("http://", "https://")):
        return DOMAIN in h            # our own absolute URLs count as internal
    return True                       # site-relative

def internal_path(href, page_rel):
    """Turn an internal href into a resolvable leading-slash path."""
    np = norm_path(href)
    if np is not None:
        return np
    # relative link: resolve against the page's directory
    base = "/" + os.path.dirname(page_rel).replace("\\", "/")
    joined = os.path.normpath(os.path.join(base, href.split("#")[0].split("?")[0])).replace("\\", "/")
    if not joined.startswith("/"):
        joined = "/" + joined
    return joined

# ---------------- sitemap + redirects ----------------

def parse_sitemaps(root, files):
    locs = []
    for rel in files:
        if re.search(r"sitemap.*\.xml$", rel, re.I):
            try:
                with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
                    locs += re.findall(r"<loc>\s*([^<]+?)\s*</loc>", fh.read(), re.I)
            except Exception:
                pass
    return locs

def parse_redirect_sources(root, files):
    srcs = []
    if "vercel.json" in files:
        try:
            with open(os.path.join(root, "vercel.json"), encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
            for r in data.get("redirects", []):
                s = r.get("source", "")
                srcs.append(s.split(":")[0].rstrip("/*"))  # static prefix of the source
        except Exception:
            pass
    return srcs

def covered_by_redirect(path, redirect_prefixes):
    return any(path == s or (s and path.startswith(s)) for s in redirect_prefixes)

# ---------------- health checks (schema + freshness) ----------------

def _read(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return ""

def _parse_date(s):
    """Parse an ISO date (YYYY-MM-DD or leading date of a datetime). None if unparseable."""
    if not s:
        return None
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except Exception:
        return None

def _parse_baked_date(text, today):
    """Turn a baked card's relative 'Posted ...' text into an approximate date.
    Mirrors bbj_feed_bake.rel_posted(): today / yesterday / N days ago / '<Mon> <D>'.
    Relative forms resolve against `today` (the audit runs ~1h after the bake, so this
    is close); the absolute '<Mon> <D>' form is exact (year chosen as most recent past)."""
    t = text.strip()
    if "today" in t:
        return today
    if "yesterday" in t:
        return today - datetime.timedelta(days=1)
    m = re.search(r"Posted (\d+) days? ago", t)
    if m:
        return today - datetime.timedelta(days=int(m.group(1)))
    m = re.search(r"Posted ([A-Z][a-z]{2}) (\d{1,2})", t)
    if m and m.group(1) in _MONTHS:
        mo, day = _MONTHS[m.group(1)], int(m.group(2))
        try:
            c = datetime.date(today.year, mo, day)
            if c > today:
                c = datetime.date(today.year - 1, mo, day)
            return c
        except ValueError:
            return None
    return None

def check_jobposting_schema(root, pages):
    """Check A. For every page carrying JobPosting JSON-LD, return (page_url, reason) for
    each: block that fails to parse, missing Google-required field, unparseable/future
    datePosted, or a validThrough that is not after today (the silent Jobs-box drop)."""
    fails = []
    today = datetime.date.today()
    for rel in pages:
        html = _read(root, rel)
        if '"JobPosting"' not in html:
            continue
        url = file_to_url(rel)
        for block in LDJSON_RE.findall(html):
            if '"JobPosting"' not in block:
                continue
            try:
                obj = json.loads(block)
            except Exception as e:
                fails.append((url, "invalid JSON-LD: " + str(e)[:80]))
                continue
            if isinstance(obj, dict) and "@graph" in obj:
                candidates = obj["@graph"]
            elif isinstance(obj, list):
                candidates = obj
            else:
                candidates = [obj]
            for o in candidates:
                if not isinstance(o, dict) or o.get("@type") != "JobPosting":
                    continue
                miss = [f for f in JOBPOSTING_REQUIRED if not o.get(f)]
                if miss:
                    fails.append((url, "missing required field(s): " + ", ".join(miss)))
                dp_raw = o.get("datePosted")
                dp = _parse_date(dp_raw)
                if dp_raw and dp is None:
                    fails.append((url, "datePosted not a valid date: %r" % dp_raw))
                elif dp and dp > today:
                    fails.append((url, "datePosted is in the future: %s" % dp.isoformat()))
                vt_raw = o.get("validThrough")
                if vt_raw:
                    vt = _parse_date(vt_raw)
                    if vt is None:
                        fails.append((url, "validThrough not a valid date: %r" % vt_raw))
                    elif vt <= today:
                        fails.append((url, "validThrough %s is not after today -> drops from Jobs box" % vt_raw))
    return fails

def check_feed_freshness(root, pages):
    """Check B. Return (item, reason) for: an active per-page feed (one a real page
    references via BBJ_FEED_KEY) or board.json whose newest posted_date is older than
    STALENESS_DAYS, empty, or undated; plus baked pages whose freshest card date lags
    the feed's freshest date by more than MAX_BAKE_LAG_DAYS (bake didn't run post-refresh)."""
    fails = []
    today = datetime.date.today()

    def feed_file(key):
        return os.path.join(root, "feed", *key.split("/")) + ".json"

    page_keys = {}   # feed key -> first page rel that uses it (active-feed set)
    baked = []       # (rel, key, html) for pages with baked cards
    for rel in pages:
        html = _read(root, rel)
        m = FEED_KEY_RE.search(html)
        if not m:
            continue
        key = m.group(1)
        page_keys.setdefault(key, rel)
        if BAKE_START in html:
            baked.append((rel, key, html))

    feed_fresh = {}  # key -> freshest date (None if empty/undated/unreadable)
    for key in page_keys:
        fp = feed_file(key)
        if not os.path.isfile(fp):
            continue   # 'missing feed' is bbj_feed_target_check.py's job, not a freshness call
        try:
            data = json.load(open(fp, encoding="utf-8"))
        except Exception as e:
            fails.append(("feed/" + key + ".json", "unreadable feed JSON: " + str(e)[:60]))
            feed_fresh[key] = None
            continue
        jobs = data.get("jobs") or []
        dates = [d for d in (_parse_date(j.get("posted_date")) for j in jobs) if d]
        if not jobs:
            fails.append(("feed/" + key + ".json", "feed has 0 jobs (page shows no listings)"))
            feed_fresh[key] = None
        elif not dates:
            fails.append(("feed/" + key + ".json", "no posted_date on any job (Google reads no date)"))
            feed_fresh[key] = None
        else:
            fresh = max(dates)
            feed_fresh[key] = fresh
            age = (today - fresh).days
            if age > STALENESS_DAYS:
                fails.append(("feed/" + key + ".json",
                              "stale: newest job %s is %dd old (> %dd)" % (fresh.isoformat(), age, STALENESS_DAYS)))

    # board.json: the whole-site board feed
    bp = os.path.join(root, "feed", "board.json")
    if os.path.isfile(bp):
        try:
            bd = json.load(open(bp, encoding="utf-8"))
            bdates = [d for d in (_parse_date(j.get("posted_date")) for j in (bd.get("jobs") or [])) if d]
            if not bdates:
                fails.append(("feed/board.json", "no dated jobs in board.json"))
            else:
                age = (today - max(bdates)).days
                if age > STALENESS_DAYS:
                    fails.append(("feed/board.json",
                                  "stale: newest job %s is %dd old (> %dd)" % (max(bdates).isoformat(), age, STALENESS_DAYS)))
        except Exception as e:
            fails.append(("feed/board.json", "unreadable: " + str(e)[:60]))

    # bake-lag sub-assertion: baked HTML must not trail its feed by > one refresh cycle
    for rel, key, html in baked:
        ff = feed_fresh.get(key)
        if not ff:
            continue   # feed empty/undated already reported; nothing to compare
        end = html.find(BAKE_END)
        block = html[html.find(BAKE_START): end if end != -1 else len(html)]
        bdates = [d for d in (_parse_baked_date(t, today) for t in POSTED_TEXT_RE.findall(block)) if d]
        if not bdates:
            continue
        lag = (ff - max(bdates)).days
        if lag > MAX_BAKE_LAG_DAYS:
            fails.append((file_to_url(rel),
                          "baked cards lag feed by %dd (feed newest %s) -> bake didn't run after refresh"
                          % (lag, ff.isoformat())))
    return fails

# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=".")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--ci", action="store_true",
                    help="run schema + freshness checks too and EXIT NON-ZERO on any failure "
                         "(broken/dead links, invalid JobPosting, stale/lagging feeds). "
                         "Without --ci the same findings print but exit stays 0.")
    ap.add_argument("--report", default=None,
                    help="write a compact JSON summary of failures (the Make.com alert payload)")
    args = ap.parse_args()
    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"Folder not found: {root}"); sys.exit(1)

    files = gather_files(root)
    pages = sorted(f for f in files if f.endswith(".html"))
    real_urls = {file_to_url(f) for f in pages}
    redirect_prefixes = parse_redirect_sources(root, files)

    broken = defaultdict(list)      # target_path -> [source pages]
    inbound = defaultdict(int)      # resolved file -> inbound internal link count
    for rel in pages:
        for href in links_on_page(root, rel):
            if not is_internal(href):
                continue
            path = internal_path(href, rel)
            hit = resolve(path, files)
            if hit:
                if hit != rel:
                    inbound[hit] += 1
            else:
                broken[path].append(rel)

    # suggest a real target for each broken path via slug-word match
    suggestions = {}
    real_by_tokens = defaultdict(list)
    for u in real_urls:
        real_by_tokens[slug_tokens(u)].append(u)
    for tgt in broken:
        toks = slug_tokens(tgt)
        if toks in real_by_tokens:                 # exact word-set match (handles reversed slugs)
            suggestions[tgt] = real_by_tokens[toks][0]
        else:
            near = get_close_matches(tgt.rstrip("/").split("/")[-1],
                                     [u.rstrip("/").split("/")[-1] for u in real_urls], n=1, cutoff=0.6)
            suggestions[tgt] = next((u for u in real_urls if u.endswith("/"+near[0])), "") if near else ""

    # sitemap checks
    locs = parse_sitemaps(root, files)
    sm_paths = set()
    dead_sitemap = []
    for loc in locs:
        pth = norm_path(loc) or loc
        sm_paths.add(pth.rstrip("/") or "/")
        if not resolve(pth, files):
            dead_sitemap.append(loc)
    missing_from_map = sorted(u for u in real_urls
                              if (u.rstrip("/") or "/") not in sm_paths) if locs else []

    # orphans: real pages nothing links to (exclude the homepage)
    orphans = sorted(file_to_url(f) for f in pages
                     if inbound.get(f, 0) == 0 and file_to_url(f) != "/")

    # ---- health checks (schema + freshness). Run in both modes; only --ci gates exit ----
    schema_fails = check_jobposting_schema(root, pages)
    freshness_fails = check_feed_freshness(root, pages)
    # Only the channel-killing link problems gate --ci: broken internal links (A) and dead
    # sitemap URLs (B). Orphans (D) and missing-from-map (C) are SEO hygiene, not 404s, and
    # stay report-only so pre-existing orphan noise never fails the alert.
    channel_link_fails = sum(len(v) for v in broken.values()) + len(dead_sitemap)

    # ---------------- report ----------------
    print("="*68)
    print(f"BBJ LINK AUDIT   ({len(pages)} pages, {len(locs)} sitemap URLs)")
    print("="*68)
    print(f"\n  A) Broken internal links : {sum(len(v) for v in broken.values())} "
          f"links -> {len(broken)} dead targets")
    print(f"  B) Dead sitemap URLs     : {len(dead_sitemap)}")
    print(f"  C) Pages missing from map: {len(missing_from_map)}"
          f"{'  (no sitemap found)' if not locs else ''}")
    print(f"  D) Orphan pages          : {len(orphans)}")
    print(f"  E) JobPosting schema     : {len(schema_fails)} issue(s)")
    print(f"  F) Feed freshness        : {len(freshness_fails)} issue(s)")

    if broken:
        print("\n" + "-"*68)
        print("A) BROKEN INTERNAL LINKS  (a page links here, but no real page exists)")
        print("   -> = suggested correct target (this is your redirect/fix map)")
        print("-"*68)
        for tgt in sorted(broken):
            via = "  [also has a redirect]" if covered_by_redirect(tgt, redirect_prefixes) else ""
            sug = suggestions.get(tgt) or "??? no close match, decide manually"
            print(f"\n  DEAD: {tgt}{via}")
            print(f"    ->  {sug}")
            for src in sorted(set(broken[tgt]))[:8]:
                print(f"    linked from: {file_to_url(src)}")
            extra = len(set(broken[tgt])) - 8
            if extra > 0:
                print(f"    ...and {extra} more pages")

    if dead_sitemap:
        print("\n" + "-"*68)
        print("B) DEAD SITEMAP URLS  (sitemap tells Google to crawl a 404)")
        print("-"*68)
        for u in dead_sitemap:
            print(f"  {u}")

    if missing_from_map:
        print("\n" + "-"*68)
        print(f"C) PAGES MISSING FROM SITEMAP  ({len(missing_from_map)})")
        print("-"*68)
        for u in missing_from_map[:40]:
            print(f"  {u}")
        if len(missing_from_map) > 40:
            print(f"  ...and {len(missing_from_map)-40} more")

    if orphans:
        print("\n" + "-"*68)
        print(f"D) ORPHAN PAGES  ({len(orphans)}) - real pages nothing links to")
        print("-"*68)
        for u in orphans[:40]:
            print(f"  {u}")
        if len(orphans) > 40:
            print(f"  ...and {len(orphans)-40} more")

    if schema_fails:
        print("\n" + "-"*68)
        print(f"E) JOBPOSTING SCHEMA  ({len(schema_fails)}) - invalid/stale JobPosting JSON-LD")
        print("   (a past validThrough or missing field silently drops the listing from Google's Jobs box)")
        print("-"*68)
        for u, why in schema_fails[:40]:
            print(f"  {u}\n     {why}")
        if len(schema_fails) > 40:
            print(f"  ...and {len(schema_fails)-40} more")

    if freshness_fails:
        print("\n" + "-"*68)
        print(f"F) FEED FRESHNESS  ({len(freshness_fails)}) - staleness > {STALENESS_DAYS}d or bake-lag > {MAX_BAKE_LAG_DAYS}d")
        print("   (a green cron that produced stale output, or a bake that didn't run after the feed refreshed)")
        print("-"*68)
        for item, why in freshness_fails[:40]:
            print(f"  {item}\n     {why}")
        if len(freshness_fails) > 40:
            print(f"  ...and {len(freshness_fails)-40} more")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["type","item","suggested_fix","linked_from"])
            for tgt in sorted(broken):
                w.writerow(["broken_link", tgt, suggestions.get(tgt,""),
                            " | ".join(sorted({file_to_url(s) for s in broken[tgt]}))])
            for u in dead_sitemap:     w.writerow(["dead_sitemap", u, "", ""])
            for u in missing_from_map: w.writerow(["missing_from_sitemap", u, "", ""])
            for u in orphans:          w.writerow(["orphan", u, "", ""])
        print(f"\nCSV written: {args.csv}")

    print("\nDone.  Fix A first (dead-ends users hit), then B, then C/D.\n")

    # ---- alert payload: compact JSON summary (counts + first ~10 failing items) ----
    if args.report:
        link_items = ([{"item": tgt, "reason": "broken internal link",
                        "linked_from": sorted({file_to_url(s) for s in broken[tgt]})[:3]}
                       for tgt in sorted(broken)]
                      + [{"item": u, "reason": "dead sitemap URL"} for u in dead_sitemap])
        payload = {
            "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ok": (channel_link_fails == 0 and not schema_fails and not freshness_fails),
            "counts": {"links": channel_link_fails,
                       "schema": len(schema_fails),
                       "freshness": len(freshness_fails)},
            "failures": {
                "links": link_items[:10],
                "schema": [{"page": u, "reason": w} for u, w in schema_fails[:10]],
                "freshness": [{"item": i, "reason": w} for i, w in freshness_fails[:10]],
            },
        }
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"Health report written: {args.report}  (ok={payload['ok']})\n")

    # ---- CI gate: exit non-zero on any channel-killing failure. Interactive stays 0. ----
    if args.ci:
        failed = channel_link_fails > 0 or bool(schema_fails) or bool(freshness_fails)
        if failed:
            print(f"CI FAIL: links={channel_link_fails} schema={len(schema_fails)} "
                  f"freshness={len(freshness_fails)}\n")
        sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
