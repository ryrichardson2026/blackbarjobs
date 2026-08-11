#!/usr/bin/env python3
"""bbj_indexing_ping.py - notify Google's Indexing API of pages whose jobs changed.

Google's Indexing API only accepts pages carrying JobPosting or BroadcastEvent
structured data. Every BBJ hub/role page emits JobPosting, so they all qualify.
This is a pure crawl-speed lever: it changes nothing on the site and adds no
pages. It only tells Google "this URL's jobs changed, recrawl it".

Why "jobs changed" and not "file changed"
-----------------------------------------
The feed bake rewrites almost every page each run (card order and the feed's
`generated` timestamp shift), so a raw file diff flags ~all 195 pages every run
and blows the 200/day publish quota on pages that did not meaningfully change.
Instead we compare the SET of jobs (by apply_link) in each page feed before and
after this run, and submit a page only when a job was ADDED or REMOVED. Pure
reordering, timestamp churn, or an edit to an existing job's text is NOT a
material change and is skipped.

What it does
------------
1. Finds the feed/<key>.json files changed in a git range (default HEAD~1..HEAD,
   the just-pushed bake commit).
2. For each, compares the apply_link set at the base ref vs the head ref. Equal
   set -> reshuffle only -> skip. Added/removed job -> material -> include.
3. Maps the feed key to its page's canonical URL via bbj_page_targets.json (key
   -> HTML path) and the page's own <link rel="canonical">.
4. HEAD-checks each URL is a live 200 (never pings a redirect source, a missing
   page, or an undeployed URL), then submits URL_UPDATED, logging each response.

Safety rails
------------
- Hard cap of 190 submissions per run (below the 200/day quota); overflow is
  logged, never silently dropped.
- 429 (quota exhausted) is a soft stop: log URLs not yet sent and exit 0.
- Missing/empty key -> log and exit 0, so the step can be wired before GCP setup.

Auth
----
Reads a Google service-account JSON key from --key / $GOOGLE_INDEXING_KEY (the
JSON itself, as stored in a GitHub Actions secret, or a path to a .json file).
The service-account email must be an Owner on the Search Console property, or the
API returns 403 "Permission denied. Failed to verify the URL ownership".

Usage
-----
  # CI: pages whose jobs changed in the last commit
  GOOGLE_INDEXING_KEY='{...}' python automation/bbj_indexing_ping.py

  # explicit range / preview
  python automation/bbj_indexing_ping.py --range HEAD~1..HEAD --dry-run

  # one-off manual submit of exact URLs (bypasses the feed-diff)
  python automation/bbj_indexing_ping.py --url https://www.blackbarjobs.com/dallas/jobs/dallas-unarmed-security
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error

API_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"  # colon, not slash
SCOPES = ["https://www.googleapis.com/auth/indexing"]
HARD_CAP = 190
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS_FILE = os.path.join(ROOT, "automation", "bbj_page_targets.json")

# A page feed lives at feed/<key>.json. Aggregate/meta feeds are not pages.
NON_PAGE_FEEDS = {"feed/_manifest.json", "feed/board.json"}

# <link rel="canonical" ...> and href may appear in either order across page
# vintages (older pages emit href first, newer ones rel first).
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
REL_CANON_RE = re.compile(r'rel=["\']canonical["\']', re.IGNORECASE)
HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


def log(msg):
    print(f"[indexing-ping] {msg}", flush=True)


def git(args):
    """Run a git command at the repo root; return stdout or None on failure."""
    try:
        return subprocess.run(
            ["git"] + args, cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None


def parse_range(range_spec):
    """'A..B' -> ('A','B'); 'C' -> ('C~1','C')."""
    if ".." in range_spec:
        base, head = range_spec.split("..", 1)
        return (base or "HEAD~1"), (head or "HEAD")
    return f"{range_spec}~1", range_spec


def changed_feed_files(base, head):
    """feed/*.json files changed between base and head (page feeds only)."""
    out = git(["diff", "--name-only", f"{base}..{head}", "--", "feed"])
    if out is None:
        log(f"git diff failed for {base}..{head}")
        return []
    files = []
    for f in out.splitlines():
        f = f.strip().replace("\\", "/")
        if f.endswith(".json") and f not in NON_PAGE_FEEDS:
            files.append(f)
    return files


def job_ids_at(ref, path):
    """Set of job identities (apply_link, or title|company|location) in the feed
    at the given git ref. Empty set if the file does not exist at that ref."""
    content = git(["show", f"{ref}:{path}"])
    if content is None:
        return set()
    try:
        d = json.loads(content)
    except json.JSONDecodeError:
        log(f"warning: {path} at {ref} is not valid JSON; treating as no jobs")
        return set()
    jobs = d.get("jobs", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
    ids = set()
    for j in jobs:
        link = (j.get("apply_link") or "").strip()
        if link:
            ids.add(link)
        else:
            ids.add("|".join(str(j.get(k, "")) for k in ("title", "company", "location")))
    return ids


def load_targets():
    """feed key -> canonical HTML path, from the canonical automation manifest."""
    with open(TARGETS_FILE, encoding="utf-8") as fh:
        t = json.load(fh)
    return {e["key"]: e["path"] for e in t.get("targets", [])}


def canonical_for_path(html_rel_path):
    """Read a page's own canonical URL. None if the file or tag is missing."""
    full = os.path.join(ROOT, html_rel_path.replace("/", os.sep))
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as fh:
            html = fh.read()
    except OSError:
        return None
    for tag in LINK_TAG_RE.findall(html):
        if REL_CANON_RE.search(tag):
            m = HREF_RE.search(tag)
            if m:
                return m.group(1).strip()
    return None


def material_urls(base, head):
    """Canonical URLs of pages whose job SET changed (added/removed) in the range."""
    feeds = changed_feed_files(base, head)
    log(f"{len(feeds)} page feed(s) changed in {base}..{head}")
    targets = load_targets()
    urls, seen = [], set()
    for path in feeds:
        key = path[len("feed/"):-len(".json")]
        old_ids = job_ids_at(base, path)
        new_ids = job_ids_at(head, path)
        added, removed = new_ids - old_ids, old_ids - new_ids
        if not added and not removed:
            continue  # reshuffle / timestamp churn only, not material
        html_path = targets.get(key)
        if not html_path:
            log(f"skip {key}: not a page target (no canonical to ping)")
            continue
        url = canonical_for_path(html_path)
        if not url:
            log(f"skip {key}: no canonical in {html_path}")
            continue
        if url not in seen:
            seen.add(url)
            urls.append(url)
        log(f"material: {key}  (+{len(added)} / -{len(removed)} jobs)  -> {url}")
    return urls


def is_live(url):
    """True only if the URL serves 200 as itself. urllib follows redirects, so we
    compare the final URL to the requested one: if it moved, this is a redirect
    source and Google should be told about the destination, not this hop."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                final = resp.geturl()
                if resp.status == 200 and final.rstrip("/") == url.rstrip("/"):
                    return True
                log(f"skip {url}: {resp.status}, resolved to {final}")
                return False
        except urllib.error.HTTPError as e:
            if e.code == 405 and method == "HEAD":
                continue  # server refuses HEAD; retry GET
            log(f"skip {url}: HTTP {e.code}")
            return False
        except urllib.error.URLError as e:
            log(f"skip {url}: {e.reason}")
            return False
    return False


def load_credentials(key_value):
    """Service-account creds from JSON content or a file path."""
    key_value = key_value.strip()
    info = json.loads(key_value) if key_value.startswith("{") else json.load(open(key_value, encoding="utf-8"))
    from google.oauth2 import service_account
    import google.auth.transport.requests as gtr
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    creds.refresh(gtr.Request())
    return creds


def publish(url, token):
    payload = json.dumps({"url": url, "type": "URL_UPDATED"}).encode("utf-8")
    req = urllib.request.Request(
        API_ENDPOINT, data=payload, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        return None, str(e.reason)


def main():
    ap = argparse.ArgumentParser(description="Ping Google Indexing API for pages whose jobs changed.")
    ap.add_argument("--range", default="HEAD~1..HEAD",
                    help="git range to diff feeds (default HEAD~1..HEAD)")
    ap.add_argument("--url", action="append", default=[],
                    help="submit this exact URL, bypassing the feed diff (repeatable)")
    ap.add_argument("--key", default=os.environ.get("GOOGLE_INDEXING_KEY", ""),
                    help="service-account JSON content or path (default $GOOGLE_INDEXING_KEY)")
    ap.add_argument("--cap", type=int, default=HARD_CAP, help=f"max submissions/run (default {HARD_CAP})")
    ap.add_argument("--no-live-check", action="store_true", help="skip the HEAD 200 pre-check")
    ap.add_argument("--dry-run", action="store_true", help="print the URL list but do not call Google")
    args = ap.parse_args()

    # 1. Build the candidate URL list.
    if args.url:
        urls = list(dict.fromkeys(args.url))
        log(f"explicit URL mode: {len(urls)} url(s)")
    else:
        base, head = parse_range(args.range)
        urls = material_urls(base, head)
        log(f"{len(urls)} page(s) with material job changes")

    if not urls:
        log("nothing to submit; exiting 0")
        return 0

    # 2. Cap, logging overflow rather than dropping it silently.
    if len(urls) > args.cap:
        deferred = urls[args.cap:]
        log(f"CAP {args.cap} exceeded: submitting {args.cap}, deferring {len(deferred)}:")
        for d in deferred:
            log(f"  deferred: {d}")
        urls = urls[:args.cap]

    # 3. Live-check so we never ping a redirect source or an undeployed page.
    if not args.no_live_check:
        live = [u for u in urls if is_live(u)]
        log(f"{len(live)}/{len(urls)} URL(s) are live 200")
        urls = live
        if not urls:
            log("no live URLs to submit; exiting 0")
            return 0

    if args.dry_run:
        log("dry-run: would submit URL_UPDATED for:")
        for u in urls:
            log(f"  {u}")
        return 0

    # 4. Auth.
    if not args.key:
        log("no GOOGLE_INDEXING_KEY provided; skipping submission (exit 0)")
        return 0
    try:
        token = load_credentials(args.key).token
    except ImportError:
        log("google-auth not installed. In CI: pip install google-auth")
        return 0  # never fail the feed workflow over indexing
    except Exception as e:
        log(f"credential load failed: {e}")
        return 0

    # 5. Submit, logging each response. 429 -> soft stop.
    ok = 0
    for i, u in enumerate(urls):
        status, body = publish(u, token)
        if status == 200:
            ok += 1
            log(f"OK   {u}")
        elif status == 429:
            remaining = urls[i:]
            log(f"429 quota exhausted at {u}. {len(remaining)} URL(s) not sent this run:")
            for r in remaining:
                log(f"  not-sent: {r}")
            log(f"submitted {ok} before quota; soft stop, exit 0")
            return 0
        elif status == 403:
            log(f"403 {u} -> {str(body).strip()[:200]}")
            log("403 usually means the service account is not an Owner on the "
                "Search Console property. Fix that, then re-run.")
        else:
            log(f"{status} {u} -> {str(body).strip()[:200]}")

    log(f"done: {ok}/{len(urls)} submitted OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
