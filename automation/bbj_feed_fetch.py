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

import argparse, hashlib, html, json, os, re, sys, time
from datetime import datetime, timedelta, timezone, date
from urllib.parse import urlencode, quote, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SEARCHAPI_URL = "https://www.searchapi.io/api/v1/search"
DEFAULT_SUPABASE_URL = "https://gbtwcawojflrfczswbch.supabase.co"
DEFAULT_QUERIES = "bbj_feed_queries.json"
# DESC_MAX is BBJ's own cap, not searchapi's — searchapi returns the full posting.
# Stored medians sat at the old 600 cap (~80% truncated). 8000 clears the observed
# real max (~14.5K is pathological; normal postings run 2-6K) while still guarding
# against a runaway response. UPSERT_BATCH dropped from 100: full descriptions make
# each row ~10x larger, so 25 keeps request bodies well under Supabase limits.
DESC_MAX = 8000
UPSERT_BATCH = 25


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
    m = re.search(r"(\d+)(\+)?\s*(hour|day|week|month|year)s?\s*ago", s)
    if not m: return None
    n, plus, unit = int(m.group(1)), bool(m.group(2)), m.group(3)
    if plus or unit in ("month", "year"):
        return None
    days = {"hour": 0, "day": n, "week": n * 7}[unit]
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

def clean_text(s):
    """Repair upstream mojibake, THEN decode HTML entities (e.g. &#8211; -> en-dash).
    Used on every human-readable field before hashing/storage."""
    if not s:
        return s
    return html.unescape(repair_mojibake(s))

def deep_clean(obj):
    """clean_text every string inside a nested json structure while preserving its
    shape. For job_highlights / extensions / detected_extensions, which we store raw
    (no reshaping) but still want mojibake- and entity-clean."""
    if isinstance(obj, str):
        return clean_text(obj)
    if isinstance(obj, list):
        return [deep_clean(x) for x in obj]
    if isinstance(obj, dict):
        return {k: deep_clean(v) for k, v in obj.items()}
    return obj


# ---- salary parsing (Task 3) ---------------------------------------------------
# Real data carries ZERO dollar signs; the old $-anchored SALARY_RE never fired on
# it. Values look like "25-50 an hour", "36K-60K a year", "77,987-134,165 a year",
# "3,120 a month", with the separator an EN-DASH (U+2013), not a hyphen. We extract
# every numeric token (so any separator works), expand K, strip commas, keep
# decimals, map the unit, and REJECT (return None) anything unparseable or implausible.
UNIT_MAP = [
    (("an hour", "per hour", "/hr", "/hour", "hourly"), "HOUR"),
    (("a year", "per year", "annually", "/yr", "/year", "yearly", "annual"), "YEAR"),
    (("a day", "per day", "/day", "daily"), "DAY"),
    (("a week", "per week", "/week", "weekly"), "WEEK"),
    (("a month", "per month", "/month", "monthly"), "MONTH"),
]
# Plausibility bands (validity check, NOT a correction): outside range -> stay null,
# never clamp. HOUR/YEAR are from the Notion $10-45 hourly band, widened; DAY/WEEK/
# MONTH derived from the same hourly floor/ceiling across a normal shift/schedule.
PAY_BOUNDS = {
    "HOUR": (7, 100),
    "DAY": (50, 1200),
    "WEEK": (200, 6000),
    "MONTH": (1000, 30000),
    "YEAR": (15000, 250000),
}
_PAY_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?[kK]?")

def _pay_number(tok):
    tok = tok.strip()
    mult = 1000 if tok[-1:] in ("k", "K") else 1
    if mult == 1000:
        tok = tok[:-1]
    tok = tok.replace(",", "")
    try:
        return float(tok) * mult
    except ValueError:
        return None

def parse_pay(raw):
    """-> {'min': float, 'max': float|None, 'currency': 'USD', 'unit': ...} or None.
    Single values set max=None (not max=min). Never guesses: unknown unit,
    no numbers, or an implausible value all return None."""
    if not raw:
        return None
    s = str(raw).strip().lower()
    unit = None
    for needles, u in UNIT_MAP:
        if any(n in s for n in needles):
            unit = u
            break
    if unit is None:
        return None
    vals = [v for v in (_pay_number(t) for t in _PAY_NUM_RE.findall(s)) if v is not None]
    if not vals:
        return None
    lo = vals[0]
    hi = vals[1] if len(vals) >= 2 else None
    if hi is not None and hi < lo:
        lo, hi = hi, lo
    low, high = PAY_BOUNDS[unit]
    if not (low <= lo <= high):
        return None
    if hi is not None and not (low <= hi <= high):
        return None
    return {"min": lo, "max": hi, "currency": "USD", "unit": unit}


# ---- apply-link ranking (Task 4) -----------------------------------------------
# 64% of apply clicks currently land on other job boards; ~9% reach an employer.
# Rank employer-owned domain > ATS domain > everything else, over the WHOLE pool
# (apply_links array PLUS the top-level apply_link, which is often NOT in the array).
# Strip Google's attribution params before storing; never use sharing_link.
ATS_DOMAINS = (
    "myworkdayjobs", "workday", "taleo", "icims", "greenhouse", "lever.co",
    "smartrecruiters", "paylocity", "paycom", "ukg", "adp", "brassring", "jobvite",
    "dayforce", "oraclecloud", "successfactors", "applytojob", "careerplug", "jazzhr",
    "joblinkapply",  # observed live; JobLink is an ATS, not in the brief's list
)
STRIP_PARAMS = {"utm_campaign", "utm_source", "utm_medium"}
# Generic company words that must NOT count as an employer-domain match, or every
# "*security*.com" job board would look employer-owned.
_GENERIC_CO_TOKENS = {
    "security", "services", "service", "staffing", "solutions", "protective",
    "protection", "universal", "global", "national", "careers", "jobs", "group",
    "company", "corporation", "corp", "inc", "llc", "ltd", "the", "and",
}

def strip_tracking(link):
    """Remove Google's utm_* attribution params, preserving everything else."""
    if not link:
        return link
    p = urlsplit(link)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if k not in STRIP_PARAMS]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), p.fragment))

def _domain(link):
    try:
        return urlsplit(link).netloc.lower()
    except ValueError:
        return ""

def _company_tokens(company):
    toks = re.findall(r"[a-z0-9]+", (company or "").lower())
    return {t for t in toks if len(t) >= 4 and t not in _GENERIC_CO_TOKENS}

def _apply_score(link, ctoks):
    reg = _domain(link)
    if reg and any(t in reg for t in ctoks):
        return 3                      # employer-owned domain
    if any(a in reg for a in ATS_DOMAINS):
        return 2                      # employer-controlled ATS
    return 1                          # job board / aggregator

def rank_apply_links(company, apply_link, apply_links):
    """Return (best_link, ranked_array). Pool = apply_links entries + top-level
    apply_link (deduped, UTM-stripped). sharing_link is never a candidate."""
    ctoks = _company_tokens(company)
    pool, seen = [], set()
    for e in (apply_links or []):
        lk = strip_tracking((e or {}).get("link"))
        if lk and lk not in seen:
            seen.add(lk)
            pool.append({"link": lk, "source": (e or {}).get("source") or _domain(lk)})
    if apply_link:
        lk = strip_tracking(apply_link)
        if lk and lk not in seen:
            seen.add(lk)
            pool.append({"link": lk, "source": _domain(lk)})
    if not pool:
        return None, []
    # stable sort: highest score first, original order preserved within a tier
    ranked = sorted(pool, key=lambda e: -_apply_score(e["link"], ctoks))
    return ranked[0]["link"], ranked


def normalize(job, qmeta, now_iso, today):
    # Clean (mojibake repair + entity decode) BEFORE hashing, so the dedupe key is
    # computed on clean text and corrupted variants collapse to one hash.
    title = clean_text(job.get("title") or "")
    company = clean_text(job.get("company_name") or "")
    location = clean_text(job.get("location") or "")
    pay = clean_text(extract_salary(job))
    # If any hashed/displayed field still carries a lost byte (U+FFFD) after repair,
    # skip the row rather than ingest corrupted text (returns None; caller drops it).
    for fld, val in (("title", title), ("company", company),
                     ("location", location), ("pay", pay)):
        if val and "�" in val:
            print("  SKIP unrepairable mojibake (%s): %r"
                  % (fld, (title or company or "")[:60]), file=sys.stderr)
            return None
    det = job.get("detected_extensions") or {}
    # Rank the whole pool (array + top-level apply_link) employer-direct first; the
    # old code just took apply_link or apply_links[0] and never chose.
    apply_link, ranked_links = rank_apply_links(
        company, job.get("apply_link"), job.get("apply_links"))
    desc = clean_text((job.get("description") or "").strip())
    if desc and "�" in desc:
        desc = ""                                   # drop unrepairable desc, keep row
    if len(desc) > DESC_MAX:
        desc = desc[:DESC_MAX].rsplit(" ", 1)[0] + "..."
    pp = parse_pay(pay)                             # structured salary, or None
    return {
        "job_hash": job_hash(company, title, location),
        "title": title, "company": company, "location": location,
        "market": qmeta["metro"], "role": qmeta["role"], "source_query": qmeta["query"],
        # Vertical is set from the QUERY, never inferred from the title (a warehouse
        # job at a hospital would misclassify). Existing security queries omit it and
        # take the 'security' default; warehouse queries carry "vertical":"warehouse".
        "vertical": qmeta.get("vertical", "security"),
        "via": clean_text(job.get("via")), "pay": pay,
        "pay_min": pp["min"] if pp else None,
        "pay_max": pp["max"] if pp else None,
        "pay_unit": pp["unit"] if pp else None,
        "schedule": det.get("schedule") or det.get("schedule_type"),
        "posted_date": parse_posted(det.get("posted_at"), today),
        "apply_link": apply_link, "sharing_link": job.get("sharing_link"),
        "apply_links": ranked_links or None,
        "job_highlights": deep_clean(job.get("job_highlights")) or None,
        "extensions": deep_clean(job.get("extensions")) or None,
        "detected_extensions": deep_clean(det) or None,
        "description": desc,
        "last_seen_at": now_iso, "updated_at": now_iso,
    }


class Supa:
    def __init__(self, base, key):
        self.rest = base.rstrip("/") + "/rest/v1"
        self.h = {"apikey": key, "Authorization": "Bearer " + key,
                  "Content-Type": "application/json"}

    def blocklist(self):
        """Return [(term, vertical, field)] triples. NULL vertical means the term
        applies to ALL verticals; a set vertical scopes suppression to matching jobs
        only (so the security blocklist never touches warehouse rows, and vice-versa).
        field is 'title' or 'company' — which column the term is matched against, so a
        staffing FIRM (which lives in company, not the title) can be suppressed."""
        st, data = http("GET", self.rest + "/feed_blocklist?select=term,vertical,field", headers=self.h)
        return ([(r["term"], r.get("vertical"), r.get("field") or "title")
                 for r in (data or [])] if isinstance(data, list) else [])

    def upsert(self, rows):
        h = dict(self.h); h["Prefer"] = "resolution=merge-duplicates,return=minimal"
        return http("POST", self.rest + "/jobs", headers=h, body=rows)

    def posted_dates(self, hashes):
        """Return {job_hash: posted_date} for existing rows among `hashes` that carry
        a non-null posted_date. The in.() filter is chunked at 200 hashes per request.
        Raises on any failed lookup so the caller can abort rather than overwrite a
        stored first-observation date with a freshly computed one."""
        out = {}
        for i in range(0, len(hashes), 200):
            chunk = hashes[i:i + 200]
            q = "job_hash=in.(" + ",".join(quote(x, safe="") for x in chunk) + ")"
            st, data = http("GET", self.rest + "/jobs?select=job_hash,posted_date&" + q,
                            headers=self.h)
            if st >= 300 or not isinstance(data, list):
                raise RuntimeError("posted_date lookup failed: %s %s" % (st, data))
            for r in data:
                if r.get("posted_date"):
                    out[r["job_hash"]] = r["posted_date"]
        return out

    def patch(self, query, body):
        h = dict(self.h); h["Prefer"] = "return=minimal"
        return http("PATCH", self.rest + "/jobs?" + query, headers=h, body=body)


def main():
    ap = argparse.ArgumentParser(description="BBJ Phase 2 fetch + upsert")
    ap.add_argument("--queries", default=DEFAULT_QUERIES)
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--market", help="filter to one metro (DFW/Houston/San Antonio/Austin/Chicago)")
    ap.add_argument("--vertical", help="filter to one vertical (security/warehouse); "
                    "queries with no vertical default to 'security'")
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
    if args.vertical:
        queries = [q for q in queries
                   if q.get("vertical", "security").lower() == args.vertical.lower()]
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
    _bl_show = ", ".join(f"{t}[{v or 'all'}/{fld}]" for t, v, fld in blocklist)
    print(f"Blocklist terms: {len(blocklist)}  ({_bl_show or 'none'})")

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

    # Preserve the FIRST observation of posted_date. The upsert runs with
    # resolution=merge-duplicates, which would recompute and overwrite posted_date
    # every run, so any label that does not age cleanly (e.g. "just posted" seen on
    # different days) drifts forward. Look up the stored posted_date for the hashes in
    # this batch and keep the stored non-null value instead of the freshly computed
    # one. If the lookup fails, abort the upsert rather than risk overwriting good
    # first-observation dates.
    try:
        stored_posted = supa.posted_dates([r["job_hash"] for r in rows])
    except Exception as e:
        print(f"posted_date lookup failed, aborting upsert: {e}", file=sys.stderr)
        sys.exit(1)
    for r in rows:
        sp = stored_posted.get(r["job_hash"])
        if sp:
            r["posted_date"] = sp

    print(f"\nUpserting {len(rows)} unique jobs ({raw_total} raw)...")
    for j in range(0, len(rows), UPSERT_BATCH):
        st, data = supa.upsert(rows[j:j+UPSERT_BATCH])
        if st >= 300:
            print(f"  upsert batch {j}: {st} {data}", file=sys.stderr)

    supa.patch(f"status=eq.inactive&suppressed=eq.false&last_seen_at=gte.{quote(now_iso)}",
               {"status": "active", "updated_at": now_iso})

    for term, vert, field in blocklist:
        # Match against title or company (whitelist the column so a bad field value can
        # never inject into the filter). NULL vertical -> suppress in every vertical; a
        # set vertical -> only that vertical's rows, so cross-vertical bleed is impossible.
        col = field if field in ("title", "company") else "title"
        q = f"suppressed=eq.false&{col}=ilike.*{quote(term)}*"
        if vert:
            q += f"&vertical=eq.{quote(vert)}"
        supa.patch(q, {"suppressed": True, "updated_at": now_iso})
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
