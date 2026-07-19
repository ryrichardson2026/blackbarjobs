#!/usr/bin/env python3
"""
bbj_feed_fetch.py  ·  Phase 2 of the BBJ Supabase feed

Pulls Google Jobs from searchapi.io for the query list in bbj_feed_queries.json,
normalizes each job to the BBJ `jobs` table shape, and upserts into Supabase.
Then it applies the keyword blocklist, reactivates anything seen this run, and
expires anything that has gone stale. This replaces the Google Sheets Apps Script.

What it does, in order, each run:
  1. Load the blocklist terms from Supabase.
  2. For every query, pull up to N pages from searchapi (default 3).
  3. Normalize + dedupe on hash(company|title|location).
  4. Upsert into jobs. The payload deliberately omits `status` and `suppressed`,
     so new rows take table defaults and existing rows keep whatever you set by
     hand. Manual kills are never overwritten.
  5. Reactivate: anything seen this run flips back to active (unless suppressed).
  6. Suppress: any job whose title matches a blocklist term is flagged suppressed.
  7. Expire: active, non-suppressed jobs not seen in 14 days, or with a posted
     date older than 30 days, flip to inactive.

Secrets come from environment variables, never from code:
  SEARCHAPI_KEY          your searchapi.io key
  SUPABASE_SERVICE_KEY   Supabase service_role key (Settings > API)
  SUPABASE_URL           optional, defaults to the BBJ project URL below

Usage (Windows PowerShell):
  $env:SEARCHAPI_KEY="..."; $env:SUPABASE_SERVICE_KEY="..."
  python bbj_feed_fetch.py --dry-run            # show planned queries, no calls
  python bbj_feed_fetch.py --market DFW         # one metro
  python bbj_feed_fetch.py                      # full weekly run
"""

import argparse, hashlib, json, os, re, sys, time
from datetime import datetime, timedelta, timezone, date
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SEARCHAPI_URL = "https://www.searchapi.io/api/v1/search"
DEFAULT_SUPABASE_URL = "https://gbtwcawojflrfczswbch.supabase.co"
DEFAULT_QUERIES = "bbj_feed_queries.json"
DESC_MAX = 600
UPSERT_BATCH = 100


def http(method, url, headers=None, body=None, retries=3, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, data=data, method=method, headers=headers or {})
            with urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8")
                return r.status, (json.loads(raw) if raw.strip() else None)
        except HTTPError as e:
            detail = ""
            try: detail = e.read().decode("utf-8")[:300]
            except Exception: pass
            last = f"HTTP {e.code}: {detail}"
            if e.code not in (429, 500, 502, 503, 504):
                return e.code, {"__error__": last}
        except (URLError, TimeoutError) as e:
            last = str(e)
        time.sleep(2 * attempt)
    return 0, {"__error__": last}


def searchapi_page(query, api_key, page_token=None):
    params = {"engine": "google_jobs", "q": query, "api_key": api_key}
    if page_token:
        params["next_page_token"] = page_token
    status, data = http("GET", SEARCHAPI_URL + "?" + urlencode(params),
                        headers={"Accept": "application/json"})
    if not data or "__error__" in (data or {}):
        return [], None, (data or {}).get("__error__", "no data")
    jobs = data.get("jobs") or []
    token = ((data.get("pagination") or {}).get("next_page_token"))
    return jobs, token, None


SALARY_RE = re.compile(r"\$[\d,]+(?:\.\d+)?(?:\s*[-\u2013to]+\s*\$?[\d,]+(?:\.\d+)?)?"
                       r"(?:\s*(?:an?|per|/)\s*(?:hour|year|hr|yr))?", re.I)

def parse_posted(raw, ref):
    if not raw: return None
    s = raw.strip().lower()
    if s in ("just posted", "today", "posted today"): return ref.isoformat()
    if s == "yesterday": return (ref - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s*(hour|day|week|month|year)s?\s*ago", s)
    if not m: return None
    n = int(m.group(1))
    days = {"hour": 0, "day": n, "week": n*7, "month": n*30, "year": n*365}[m.group(2)]
    return (ref - timedelta(days=days)).isoformat()

def extract_salary(job):
    det = job.get("detected_extensions") or {}
    if det.get("salary"): return str(det["salary"])
    for ext in job.get("extensions") or []:
        if isinstance(ext, str) and "$" in ext:
            m = SALARY_RE.search(ext)
            return (m.group(0).strip() if m else ext.strip())
    return None

def job_hash(company, title, location):
    basis = "|".join(re.sub(r"\s+", " ", (x or "").strip().lower())
                     for x in (company, title, location))
    return hashlib.sha1(basis.encode()).hexdigest()[:12]

# Telltale bytes of UTF-8 text that was mis-decoded as cp1252/latin-1 upstream
# (searchapi returns some already double-encoded). None of these open a clean
# English job string: "â€" -> smart quotes/dashes, "Ã"/"Â" -> accented letters.
_MOJIBAKE_HINT = ("â€", "Ã", "Â")   # â€ , Ã , Â

def repair_mojibake(s):
    """Repair classic UTF-8-as-cp1252 double-encoding (â€" -> —, Ã© -> é, Â  -> nbsp,
    etc.) by re-encoding to cp1252 and decoding as UTF-8. Only attempted when a
    telltale sequence is present, and only kept if the round-trip succeeds cleanly;
    otherwise the original is returned untouched. A residual U+FFFD means bytes were
    truly lost upstream and cannot be recovered — the caller drops such rows."""
    if not s:
        return s
    s = str(s)
    if not any(h in s for h in _MOJIBAKE_HINT):
        return s
    try:
        return s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s

def normalize(job, qmeta, now_iso, today):
    # Repair mojibake BEFORE hashing, so the dedupe key is computed on clean text
    # and corrupted variants collapse to one hash instead of splitting.
    title = repair_mojibake(job.get("title") or "")
    company = repair_mojibake(job.get("company_name") or "")
    location = repair_mojibake(job.get("location") or "")
    pay = repair_mojibake(extract_salary(job))
    # If any hashed/displayed field still carries a lost byte (U+FFFD) after repair,
    # skip the row rather than ingest corrupted text (returns None; caller drops it).
    for fld, val in (("title", title), ("company", company),
                     ("location", location), ("pay", pay)):
        if val and "�" in val:
            print("  SKIP unrepairable mojibake (%s): %r"
                  % (fld, (title or company or "")[:60]), file=sys.stderr)
            return None
    det = job.get("detected_extensions") or {}
    apply_link = job.get("apply_link")
    links = job.get("apply_links") or []
    if not apply_link and links:
        apply_link = links[0].get("link")
    desc = repair_mojibake((job.get("description") or "").strip())
    if "�" in desc:
        desc = ""                                   # drop unrepairable desc, keep row
    if len(desc) > DESC_MAX:
        desc = desc[:DESC_MAX].rsplit(" ", 1)[0] + "..."
    return {
        "job_hash": job_hash(company, title, location),
        "title": title, "company": company, "location": location,
        "market": qmeta["metro"], "role": qmeta["role"], "source_query": qmeta["query"],
        "via": job.get("via"), "pay": pay,
        "schedule": det.get("schedule") or det.get("schedule_type"),
        "posted_date": parse_posted(det.get("posted_at"), today),
        "apply_link": apply_link, "sharing_link": job.get("sharing_link"),
        "description": desc,
        "last_seen_at": now_iso, "updated_at": now_iso,
    }


class Supa:
    def __init__(self, base, key):
        self.rest = base.rstrip("/") + "/rest/v1"
        self.h = {"apikey": key, "Authorization": "Bearer " + key,
                  "Content-Type": "application/json"}

    def blocklist(self):
        st, data = http("GET", self.rest + "/feed_blocklist?select=term", headers=self.h)
        return [r["term"] for r in (data or [])] if isinstance(data, list) else []

    def upsert(self, rows):
        h = dict(self.h); h["Prefer"] = "resolution=merge-duplicates,return=minimal"
        return http("POST", self.rest + "/jobs", headers=h, body=rows)

    def patch(self, query, body):
        h = dict(self.h); h["Prefer"] = "return=minimal"
        return http("PATCH", self.rest + "/jobs?" + query, headers=h, body=body)


def main():
    ap = argparse.ArgumentParser(description="BBJ Phase 2 fetch + upsert")
    ap.add_argument("--queries", default=DEFAULT_QUERIES)
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--market", help="filter to one metro (DFW/Houston/San Antonio/Austin)")
    ap.add_argument("--limit", type=int, help="cap number of queries (testing)")
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--staleness-days", type=int, default=14)
    ap.add_argument("--max-posted-age", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    spec = json.load(open(args.queries, encoding="utf-8"))
    queries = spec["queries"]
    if args.market:
        queries = [q for q in queries if q["metro"].lower() == args.market.lower()]
    if args.limit:
        queries = queries[: args.limit]
    if not queries:
        print("No queries matched.", file=sys.stderr); sys.exit(1)

    if args.dry_run:
        print(f"[dry-run] {len(queries)} queries, {args.pages} pages each "
              f"= up to {len(queries)*args.pages} pulls")
        for q in queries[:40]:
            print(f"  {q['metro']:<12} {q['query']}")
        if len(queries) > 40: print(f"  ... +{len(queries)-40} more")
        return

    api_key = os.environ.get("SEARCHAPI_KEY")
    svc_key = os.environ.get("SUPABASE_SERVICE_KEY")
    base = os.environ.get("SUPABASE_URL", DEFAULT_SUPABASE_URL)
    if not api_key or not svc_key:
        print("Missing SEARCHAPI_KEY or SUPABASE_SERVICE_KEY in environment.", file=sys.stderr)
        sys.exit(1)

    supa = Supa(base, svc_key)
    run_start = datetime.now(timezone.utc)
    now_iso = run_start.isoformat()
    today = date.today()
    blocklist = supa.blocklist()
    print(f"Blocklist terms: {len(blocklist)}  ({', '.join(blocklist) or 'none'})")

    seen, buffer = set(), {}
    raw_total, errors, skipped_mojibake = 0, [], 0
    for i, q in enumerate(queries, 1):
        token, got = None, 0
        for page in range(args.pages):
            jobs, token, err = searchapi_page(q["query"], api_key, token)
            if err:
                errors.append({"query": q["query"], "error": err}); break
            for job in jobs:
                row = normalize(job, q, now_iso, today)
                if row is None:                     # dropped: unrepairable mojibake
                    skipped_mojibake += 1
                    continue
                buffer[row["job_hash"]] = row
                seen.add(row["job_hash"])
            got += len(jobs); raw_total += len(jobs)
            if not token or not jobs: break
            time.sleep(args.sleep)
        print(f"[{i}/{len(queries)}] {q['metro']:<12} {got:>3} jobs  {q['query']}")
        time.sleep(args.sleep)

    rows = list(buffer.values())
    print(f"\nUpserting {len(rows)} unique jobs ({raw_total} raw)...")
    for j in range(0, len(rows), UPSERT_BATCH):
        st, data = supa.upsert(rows[j:j+UPSERT_BATCH])
        if st >= 300:
            print(f"  upsert batch {j}: {st} {data}", file=sys.stderr)

    supa.patch(f"status=eq.inactive&suppressed=eq.false&last_seen_at=gte.{quote(now_iso)}",
               {"status": "active", "updated_at": now_iso})

    for term in blocklist:
        supa.patch(f"suppressed=eq.false&title=ilike.*{quote(term)}*",
                   {"suppressed": True, "updated_at": now_iso})
    if blocklist:
        print("Applied blocklist suppression.")

    cutoff_seen = (run_start - timedelta(days=args.staleness_days)).isoformat()
    cutoff_post = (today - timedelta(days=args.max_posted_age)).isoformat()
    supa.patch(
        "status=eq.active&suppressed=eq.false&"
        f"or=(last_seen_at.lt.{quote(cutoff_seen)},posted_date.lt.{quote(cutoff_post)})",
        {"status": "inactive", "updated_at": now_iso})

    print(f"\nDone. {len(rows)} unique jobs this run, {len(errors)} query errors, "
          f"{skipped_mojibake} dropped for unrepairable mojibake.")
    print(f"Expiry: inactive if unseen since {cutoff_seen[:10]} or posted before {cutoff_post}.")
    if errors:
        print("First errors:", json.dumps(errors[:3], indent=2))


if __name__ == "__main__":
    main()
