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

import os, re, csv, json, argparse, sys
from difflib import get_close_matches
from collections import defaultdict

DOMAIN = "blackbarjobs.com"
SKIP_DIRS = {".git", "node_modules", ".vercel", ".github"}

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

# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=".")
    ap.add_argument("--csv", default=None)
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

if __name__ == "__main__":
    main()
