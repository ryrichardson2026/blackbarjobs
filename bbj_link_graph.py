#!/usr/bin/env python3
"""
bbj_link_graph.py — build the internal-link graph across all pages and report
the things that hurt crawl coverage: orphan pages (nothing links TO them),
pages unreachable from the market hubs, and dead links (href to a missing page).

Run from repo root:
    python3 bbj_link_graph.py .

Outputs a summary to stdout and link_graph.csv (per-page inbound/outbound counts).
"""
import os, re, csv, sys
from collections import defaultdict, deque

EXCLUDE_DIRS = {".git", "node_modules", ".vercel", ".next", "dist"}
HOSTS = ["https://www.blackbarjobs.com", "http://www.blackbarjobs.com",
         "https://blackbarjobs.com", "http://blackbarjobs.com"]
ENTRY_POINTS = ["/", "/security-jobs-dfw", "/houston", "/san-antonio", "/austin"]
HREF = re.compile(r'<a\b[^>]*\bhref\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)

def file_to_url(path):
    p = path.replace(os.sep, "/")
    if p.startswith("./"): p = p[2:]
    if p.endswith(".html"): p = p[:-5]
    if p == "index": return "/"
    if p.endswith("/index"): p = p[:-6]
    return "/" + p

def norm_link(href):
    h = href.strip()
    if not h or h[0] in "#?" or h.startswith(("mailto:", "tel:", "javascript:")):
        return None
    h = h.split("#")[0].split("?")[0]
    if not h: return None
    if h.startswith(("http://", "https://")):
        for host in HOSTS:
            if h.startswith(host):
                h = h[len(host):] or "/"; break
        else:
            return None            # external site
    if h.startswith("//"): return None
    if not h.startswith("/"): return None   # unresolved relative — rare here
    if h.endswith(".html"):
        h = h[:-5]
        if h.endswith("/index"): h = h[:-6] or "/"
    if h != "/": h = h.rstrip("/")
    return h or "/"

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    pages = {}                       # url -> file
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in EXCLUDE_DIRS]
        for f in fn:
            if f.endswith(".html"):
                fp = os.path.join(dp, f)
                pages[file_to_url(fp)] = fp
    urls = set(pages)

    outbound = defaultdict(set)      # url -> set(target urls, internal & live)
    dead = defaultdict(set)          # url -> set(dead targets)
    for url, fp in pages.items():
        html = open(fp, encoding="utf-8", errors="replace").read()
        for raw in HREF.findall(html):
            t = norm_link(raw)
            if t is None: continue
            if t in urls:
                if t != url: outbound[url].add(t)
            else:
                dead[url].add(t)

    inbound = defaultdict(set)
    for src, tgts in outbound.items():
        for t in tgts:
            inbound[t].add(src)

    # reachability BFS from entry points
    reachable, q = set(), deque()
    for e in ENTRY_POINTS:
        if e in urls: reachable.add(e); q.append(e)
    while q:
        for t in outbound[q.popleft()]:
            if t not in reachable: reachable.add(t); q.append(t)

    orphans = sorted(u for u in urls if not inbound[u] and u not in ENTRY_POINTS)
    unreachable = sorted(urls - reachable)
    dead_pairs = sorted((s, t) for s, ts in dead.items() for t in ts)

    with open("link_graph.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["url", "inbound", "outbound", "reachable", "orphan"])
        for u in sorted(urls):
            w.writerow([u, len(inbound[u]), len(outbound[u]),
                        u in reachable, (not inbound[u] and u not in ENTRY_POINTS)])

    print(f"pages: {len(urls)}   internal links: {sum(len(v) for v in outbound.values())}")
    print(f"reachable from hubs: {len(reachable)}/{len(urls)}")
    print("\n== ORPHANS (0 inbound links — crawlers can't discover via the mesh):", len(orphans))
    for u in orphans[:60]: print("   ", u)
    if len(orphans) > 60: print(f"    …+{len(orphans)-60} more (see link_graph.csv)")
    print("\n== UNREACHABLE from hubs within the link graph:", len(unreachable))
    for u in unreachable[:40]: print("   ", u)
    if len(unreachable) > 40: print(f"    …+{len(unreachable)-40} more")
    print("\n== DEAD internal links (href -> page that doesn't exist):", len(dead_pairs))
    seen = set()
    for s, t in dead_pairs:
        if t not in seen:
            seen.add(t)
            print(f"    {t}   (e.g. linked from {s})")
        if len(seen) >= 40: break
    if len(seen) >= 40: print("    …more — see below")
    # distribution of inbound links
    buckets = defaultdict(int)
    for u in urls:
        n = len(inbound[u])
        buckets["0" if n==0 else "1-2" if n<=2 else "3-5" if n<=5 else "6+"] += 1
    print("\n== inbound-link distribution:", dict(buckets))
    print("full per-page graph -> link_graph.csv")

if __name__ == "__main__":
    main()
