#!/usr/bin/env python3
"""
bbj_feed_snapshot.py  ·  Phase 3 of the BBJ Supabase feed

Reads the active jobs out of Supabase once, then for every feed page in
bbj_page_targets.json it selects the matching jobs, ranks them, caps at 5, tops
up from the metro pool when the exact match is thin, and writes one small JSON
file per page into ./feed/. Your pages will read those static files (Phase 5),
so a visitor never touches Supabase or the API.

Matching is done on the job's title and location, not on which query stored it,
using the same word-boundary logic as the taxonomy (so "unarmed" never matches
"armed"). Each page:
  - exact  = market jobs whose title matches the page role and/or whose location
             matches the page city, per the page's target_type
  - fallback = remaining active jobs in the same metro, used only to fill to 5
Ranking (approved): dated jobs first, newest first; undated jobs after; a real
salary and a working apply link break ties so the top of each feed looks richest.

Run it after a fetch:
  $env:SUPABASE_SERVICE_KEY="..."
  python bbj_feed_snapshot.py                 # build all pages into ./feed/
  python bbj_feed_snapshot.py --market DFW    # one metro
  python bbj_feed_snapshot.py --out ../feed   # write somewhere else
"""

import argparse, json, os, re, sys
from datetime import datetime, timezone, date
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

DEFAULT_SUPABASE_URL = "https://gbtwcawojflrfczswbch.supabase.co"
DEFAULT_TARGETS = "bbj_page_targets.json"
DEFAULT_OUT = "feed"
CAP = 10
CITY_ROLE_RELAX = True   # if a city-role page is thin, allow role-only-in-market before generic fallback

# canonical role -> word-boundary pattern for title matching (unarmed before armed handled by explicit checks)
ROLE_PATTERNS = {
 "armed-overnight": r"\barmed\b.*\bovernight\b|\bovernight\b.*\barmed\b",
 "unarmed": r"\bunarmed\b", "armed": r"\barmed\b", "overnight": r"\bovernight\b|\bnight\b",
 "event": r"\bevent\b", "hotel": r"\bhotel\b|\bhospitality\b",
 "hospital-healthcare": r"\bhospital\b|\bhealthcare\b|\bmedical\b",
 "warehouse": r"\bwarehouse\b|\bdistribution\b", "loss-prevention": r"\bloss\s*prevention\b|\basset\s*protection\b",
 "mobile-patrol": r"\bmobile\b|\bpatrol\b", "retail": r"\bretail\b", "construction": r"\bconstruction\b",
 "school": r"\bschool\b", "university": r"\buniversity\b|\bcollege\b|\bcampus\b", "corporate": r"\bcorporate\b",
 "residential": r"\bresidential\b|\bapartment\b|\bcommunity\b", "executive-protection": r"\bexecutive\b|\bclose\s*protection\b",
 "surveillance": r"\bsurveillance\b|\bcctv\b|\bmonitor", "airport-tsa": r"\btsa\b|\bairport\b|\baviation\b",
 "data-center": r"\bdata\s*center\b", "industrial": r"\bindustrial\b|\bplant\b", "parking": r"\bparking\b",
 "bar-club": r"\bbar\b|\bclub\b|\bnightclub\b|\bbouncer\b", "festival": r"\bfestival\b|\bconcert\b",
 "sporting-event": r"\bstadium\b|\barena\b|\bsport", "government": r"\bgovernment\b|\bfederal\b|\bmunicipal\b",
 "no-experience": r"\bno\s*experience\b|\bentry\b", "entry-level": r"\bentry\b|\bno\s*experience\b",
 "part-time": r"\bpart[\s-]?time\b", "full-time": r"\bfull[\s-]?time\b", "weekend": r"\bweekend\b",
 "night-shift": r"\bnight\b|\bovernight\b", "level-2": r"\blevel\s*2\b|\blevel\s*ii\b",
 "level-3": r"\blevel\s*3\b|\blevel\s*iii\b", "hiring-immediately": r"\bimmediate", "security-officer": r".",
}
def role_re(role):
    pat = ROLE_PATTERNS.get(role)
    return re.compile(pat, re.I) if pat else None

def city_str(token):
    return (token or "").replace("-", " ").lower()


# Supabase market label -> board.json slug (DFW is the only non-lowercase-hyphen case)
MARKET_SLUG = {"DFW": "dallas"}
def market_slug(m):
    m = (m or "").strip()
    return MARKET_SLUG.get(m, m.lower().replace(" ", "-"))


# ---------- Supabase read -----------------------------------------------------
def fetch_active_jobs(base, key):
    rest = base.rstrip("/") + "/rest/v1"
    headers = {"apikey": key, "Authorization": "Bearer " + key}
    cols = ("job_hash,title,company,location,market,role,vertical,pay,pay_min,pay_max,pay_unit,"
            "schedule,posted_date,apply_link,via,description,last_seen_at")
    out, offset, page = [], 0, 1000
    while True:
        url = (f"{rest}/jobs?select={cols}&status=eq.active&suppressed=eq.false"
               f"&order=posted_date.desc.nullslast&limit={page}&offset={offset}")
        try:
            with urlopen(Request(url, headers=headers), timeout=60) as r:
                batch = json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            detail = ""
            try: detail = e.read().decode("utf-8")[:300]
            except Exception: pass
            print(f"Supabase read error {e.code}: {detail}", file=sys.stderr); sys.exit(1)
        except URLError as e:
            print(f"Supabase connection error: {e}", file=sys.stderr); sys.exit(1)
        out.extend(batch)
        if len(batch) < page: break
        offset += page
    return out


# ---------- ranking -----------------------------------------------------------
def rank_key(job):
    pd = job.get("posted_date")
    dated = 0 if pd else 1
    try:
        ordv = -date.fromisoformat(pd).toordinal() if pd else 0
    except Exception:
        ordv = 0; dated = 1
    has_pay = 0 if job.get("pay") else 1
    has_apply = 0 if job.get("apply_link") else 1
    return (dated, ordv, has_pay, has_apply)


# ---------- selection per page ------------------------------------------------
def select_for_page(page, market_jobs):
    role = page.get("role"); city = city_str(page.get("city"))
    tt = page.get("target_type")
    rre = role_re(role) if role else None

    def title_ok(j): return bool(rre and rre.search(j.get("title") or ""))
    def city_ok(j): return bool(city and city in (j.get("location") or "").lower())

    if tt == "role":
        exact = [j for j in market_jobs if title_ok(j)]
    elif tt == "city":
        exact = [j for j in market_jobs if city_ok(j)]
    elif tt == "city-role":
        exact = [j for j in market_jobs if title_ok(j) and city_ok(j)]
        if CITY_ROLE_RELAX and len(exact) < CAP:
            have = {j["job_hash"] for j in exact}
            exact += [j for j in market_jobs if title_ok(j) and j["job_hash"] not in have]
    else:  # general
        exact = list(market_jobs)

    exact.sort(key=rank_key)
    chosen = exact[:CAP]
    n_exact = len(chosen)

    if len(chosen) < CAP:  # top up from the metro pool
        have = {j["job_hash"] for j in chosen}
        pool = sorted([j for j in market_jobs if j["job_hash"] not in have], key=rank_key)
        chosen += pool[: CAP - len(chosen)]
    return chosen, n_exact


def render_job(j):
    # vertical + role + structured pay (pay_min/max/unit) are emitted so the board and
    # hub pages can filter on the two axes and compare pay across units. Old readers
    # ignore the extra keys; the visible card fields are unchanged.
    return {k: j.get(k) for k in
            ("title", "company", "location", "vertical", "role",
             "pay", "pay_min", "pay_max", "pay_unit",
             "schedule", "posted_date", "apply_link", "via", "description")}


def main():
    ap = argparse.ArgumentParser(description="BBJ Phase 3 snapshot builder")
    ap.add_argument("--targets", default=DEFAULT_TARGETS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--market", help="filter to one metro")
    ap.add_argument("--url", default=os.environ.get("SUPABASE_URL", DEFAULT_SUPABASE_URL))
    args = ap.parse_args()

    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not key:
        print("Missing SUPABASE_SERVICE_KEY in environment.", file=sys.stderr); sys.exit(1)

    targets = json.load(open(args.targets, encoding="utf-8"))["targets"]
    if args.market:
        targets = [t for t in targets if t["market"].lower() == args.market.lower()]

    jobs = fetch_active_jobs(args.url, key)
    by_market = {}
    for j in jobs:
        by_market.setdefault(j["market"], []).append(j)
    print(f"Loaded {len(jobs)} active jobs: " +
          ", ".join(f"{m}={len(v)}" for m, v in by_market.items()))

    now = datetime.now(timezone.utc).isoformat()
    summary = {"generated": now, "pages": 0, "empty": [], "fallback_heavy": []}
    for t in targets:
        market_jobs = by_market.get(t["market"], [])
        chosen, n_exact = select_for_page(t, market_jobs)
        rel = os.path.join(args.out, t["key"] + ".json")
        os.makedirs(os.path.dirname(rel), exist_ok=True)
        with open(rel, "w", encoding="utf-8") as f:
            json.dump({"generated": now, "page": t["key"], "market": t["market"],
                       "target": t["target_type"], "count": len(chosen),
                       "exact": n_exact, "jobs": [render_job(j) for j in chosen]},
                      f, indent=2, ensure_ascii=False)
        summary["pages"] += 1
        if len(chosen) == 0:
            summary["empty"].append(t["key"])
        elif n_exact == 0:
            summary["fallback_heavy"].append(t["key"])

    # ---- master board feed: ONLY the most recent live pull, deduped by apply_link ----
    # board.json = the current pull, NOT cumulative active history. The reference is
    # the newest last_seen_at across active rows: the latest fetch stamps every job it
    # saw this run with the same timestamp, so rows last seen before that date were not
    # in the current pull and are excluded. posted_date is also required — a row with
    # no posted date has no freshness guarantee and no valid JobPosting.datePosted.
    _seen = [j.get("last_seen_at") for j in jobs if j.get("last_seen_at")]
    ref_date = max(_seen)[:10] if _seen else None
    board = []
    seen_apply = set()
    for j in sorted(jobs, key=rank_key):
        if ref_date and (j.get("last_seen_at") or "")[:10] < ref_date:
            continue                                    # not in the most recent pull
        if not j.get("posted_date"):
            continue                                    # no freshness / no datePosted
        al = j.get("apply_link")
        if al and al in seen_apply:
            continue
        if al:
            seen_apply.add(al)
        row = render_job(j)
        row["market"] = market_slug(j.get("market"))
        board.append(row)

    _bym = {}
    for r in board:
        _bym[r["market"]] = _bym.get(r["market"], 0) + 1
    bym_str = ", ".join("%s=%d" % (k, _bym[k]) for k in sorted(_bym))
    # Projection BEFORE writing (step 4). A real current pull should land in a sane
    # band; well outside it means the last_seen_at assumption is off or the pull was
    # partial, so refuse to overwrite the good board with a bad run.
    print("board projection: %d rows  (last_seen>=%s, posted_date not null)  [%s]" %
          (len(board), ref_date, bym_str))
    if len(board) < 200 or len(board) > 3000:
        print("STOP: projected board size %d is outside the expected 200-3000 band; "
              "NOT overwriting board.json (partial pull or wrong assumption). Review first."
              % len(board), file=sys.stderr)
    else:
        with open(os.path.join(args.out, "board.json"), "w", encoding="utf-8") as f:
            json.dump({"generated": now, "count": len(board), "jobs": board},
                      f, indent=2, ensure_ascii=False)
        print("Wrote board.json: %d jobs (%s)" % (len(board), bym_str))

    with open(os.path.join(args.out, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nWrote {summary['pages']} page feeds to {args.out}/")
    print(f"Empty (alert-state) pages: {len(summary['empty'])}")
    print(f"Fully-fallback pages (no exact match): {len(summary['fallback_heavy'])}")
    if summary["empty"]:
        print("  empty:", ", ".join(summary["empty"][:8]) + (" ..." if len(summary["empty"]) > 8 else ""))


if __name__ == "__main__":
    main()
