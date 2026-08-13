#!/usr/bin/env python3
"""
bbj_hub_build.py  ·  Board-based hub page builder (Task 2, corrected)

A warehouse hub is NOT the security landing template. It is the SAME job board built
in Task 1 (js/bbj-board.js), pre-filtered via window.BBJ_BOARD_PRESET to the hub's
vertical + metro + modifier, with all search / filters / chips visible and functional.
FAQ, the pay section, and requirements sit BELOW the board. A branded navy/gold header
band (no photo) stands in until a warehouse image exists.

The board skeleton (filter bar, chips, results/context bar, more-filters modal, feed,
load-more, gate/alerts modals, #jsonld) is spliced verbatim out of job-board.html at
build time, so there is ONE source of truth for the board markup — this file never
duplicates or forks it.

Reuses from bbj_feed_bake: build_job_postings + render_job_schema (baked, crawlable
JobPosting = the Google Jobs channel), pay_stats + render_pay_html (the pay section),
and the SCHEMA / PAY markers so the cron can refresh both. The build-time gate
(bbj_hub_gate) decides which hubs ship.

Usage (from repo root):
  python bbj_hub_build.py automation/build/chicago-warehouse.json --feed-dir feed --write
"""

import argparse, html as _html, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
from bbj_feed_bake import (build_job_postings, render_job_schema, pay_range_stats, render_pay_range,
                           role_pay_rows, employer_rows,
                           SCHEMA_START, SCHEMA_END, PAY_START, PAY_END)
import bbj_hub_gate as gate

GTM_ID, CLARITY, ADS_ID = "GTM-TP9JXK39", "wvxhs1xht1", "AW-17039190320"
BASE_URL = "https://www.blackbarjobs.com"

# Board role key each hub pre-filters to (board TAXONOMY warehouse role keys / shift keys)
FEEDROLE_TO_PRESET = {
    "warehouse-associate": ("role", "associate"),
    "forklift":            ("role", "forklift"),
    "package-handler":     ("role", "package-handler"),
    "overnight":           ("shift", "overnight"),
    "part-time":           ("shift", "part-time"),
}


def esc(s):
    return _html.escape("" if s is None else str(s), quote=True)


def extract_board_skeleton(board_html):
    """Splice the exact board skeleton out of job-board.html: the filter bar through the
    load-more button, and the gate/alerts modals + #jsonld container. Single source of
    truth — the hub reuses the working board's own markup."""
    a = board_html.index("<!-- FILTER BAR -->")
    b = board_html.index("<!-- CLOSING ALERT CTA")
    filters_block = board_html[a:b].rstrip()
    m = board_html.index('<div class="modal-overlay" id="gateModal"')
    # Stop BEFORE #jsonld-static: that block is the board's own security WebSite+FAQPage
    # schema and must NOT land on a warehouse hub (the hub emits its own FAQPage). Keep
    # the gate/alerts modals, then append the empty #jsonld injector container.
    j = board_html.index('<!-- Static structured data')   # the comment right before #jsonld-static
    modals_block = board_html[m:j].rstrip() + '\n<div id="jsonld" style="display:none"></div>'
    return filters_block, modals_block


def faqpage_jsonld(faqs):
    return json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]},
        ensure_ascii=False)


def breadcrumb_jsonld(cfg):
    name = cfg.get("breadcrumb_hub_name", "Chicago Warehouse Jobs")
    slug = cfg.get("breadcrumb_hub_slug", "/chicago/warehouse-jobs-chicago")
    items = [{"@type": "ListItem", "position": 1, "name": "BlackBarJobs", "item": BASE_URL}]
    if slug != cfg["slug"]:
        items.append({"@type": "ListItem", "position": 2, "name": name, "item": BASE_URL + slug})
    items.append({"@type": "ListItem", "position": len(items) + 1, "name": cfg["role"],
                  "item": BASE_URL + cfg["slug"]})
    return json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList",
                       "itemListElement": items}, ensure_ascii=False)


def preset_for(cfg):
    p = {"vertical": "warehouse", "metro": "chicago"}
    kind_key = FEEDROLE_TO_PRESET.get(cfg.get("feed_role"))
    if kind_key:
        p[kind_key[0]] = kind_key[1]
    return p


def load_feed_jobs(feed_dir, feed_key):
    fp = Path(feed_dir) / (feed_key + ".json")
    if not fp.exists():
        return []
    return (json.loads(fp.read_text(encoding="utf-8")).get("jobs") or [])


def load_metro_pay_set(feed_dir, vertical, metro):
    """The FULL vertical+metro set from board.json (the honest pay sample), not the hub's
    ~30-job feed. All Chicago warehouse hubs therefore share one metro-wide pay band."""
    fp = Path(feed_dir) / "board.json"
    if not fp.exists():
        return []
    jobs = json.loads(fp.read_text(encoding="utf-8")).get("jobs") or []
    metro = (metro or "").lower()
    return [j for j in jobs
            if j.get("vertical") == vertical and (j.get("market") or "").lower() == metro]


# Job-role display labels for the by-role pay table (job TYPES only; shift/attribute
# "roles" like overnight are deliberately excluded so the table stays honest).
WH_ROLE_DISPLAY = {
    "forklift":            "Forklift operator",
    "package-handler":     "Package handler",
    "warehouse-associate": "Warehouse associate",
    "warehouse-general":   "General warehouse",
}

# Defensive employer blocklist (the ingest layer already filters staffing firms; this only
# catches names it missed). Kept small on purpose.
WH_EMPLOYER_BLOCKLIST = []

MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def bake_date(feed_dir):
    """'as of' date stated on the page, read from board.json's generated stamp so the
    figures and the date always agree. Falls back to empty (section omits the date)."""
    p = Path(feed_dir) / "board.json"
    if not p.exists():
        return ""
    stamp = (json.loads(p.read_text(encoding="utf-8")).get("generated") or "")[:10]
    try:
        y, m, d = stamp.split("-")
        return "%s %d" % (MONTHS[int(m)], int(d))
    except Exception:
        return ""


def _money(v):
    return "$%.2f" % v if v is not None else ""


def render_dtable(headers, rows):
    """Generic data table. rows = list of tuples; a cell may be (main, sub) for a stacked
    label, or a plain string/number. Empty rows -> '' so the caller can omit the section."""
    if not rows:
        return ""
    head = "".join("<th>%s</th>" % esc(h) for h in headers)
    body = ""
    for r in rows:
        tds = ""
        for c in r:
            if isinstance(c, tuple):
                main, sub = c
                tds += '<td>%s<span class="sub">%s</span></td>' % (esc(main), esc(sub))
            elif isinstance(c, dict) and "b" in c:      # {"b": bold value}
                tds += "<td><b>%s</b></td>" % esc(c["b"])
            else:
                tds += "<td>%s</td>" % esc(c)
        body += "<tr>%s</tr>" % tds
    return ('<table class="dtable"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
            % (head, body))


def render_ladder(steps):
    """Numbered process/role ladder. steps = list of (title, detail)."""
    if not steps:
        return ""
    lis = "".join("<li><b>%s</b><span>%s</span></li>" % (esc(t), esc(d)) for t, d in steps)
    return '<ol class="ladder">%s</ol>' % lis


def render_faq(faqs):
    """Collapsible FAQ matching the mock (<details>/<summary>). Returns '' if none."""
    if not faqs:
        return ""
    items = "".join(
        '<details><summary>%s</summary><div class="ans"><p>%s</p></div></details>'
        % (esc(q), esc(a)) for q, a in faqs)
    return '<div class="faq">%s</div>' % items


def build_hub(cfg, feed_dir, board_html):
    filters_block, modals_block = extract_board_skeleton(board_html)
    slug = cfg["slug"]; title = cfg["title"]; meta = cfg["meta_desc"]
    canonical = BASE_URL + slug
    feed_key = cfg.get("feed_key", slug.lstrip("/"))
    feed_jobs = load_feed_jobs(feed_dir, feed_key)

    objs, _dropped = build_job_postings(feed_jobs)
    baked_schema = SCHEMA_START + render_job_schema(objs) + SCHEMA_END

    preset = preset_for(cfg)

    # Baked range-bar pay panel across the FULL Chicago warehouse set (not this hub's feed),
    # spliced into the board skeleton's #payWrap. data-* attrs let the cron recompute the
    # identical metro-wide band on refresh (bbj_feed_bake.splice_pay reads board.json).
    pay_vertical = preset.get("vertical", "warehouse")
    pay_metro = preset.get("metro", "chicago")
    pay_title = cfg.get("pay_h2", "Typical Warehouse Pay in Chicago, IL")
    metro_set = load_metro_pay_set(feed_dir, pay_vertical, pay_metro)
    pay_inner = render_pay_range(pay_range_stats(metro_set), pay_title)
    baked_paywrap = ('<section id="payWrap"><div class="paypanel" data-pay-vertical="%s" '
                     'data-pay-metro="%s" data-pay-title="%s">%s%s%s</div></section>'
                     % (esc(pay_vertical), esc(pay_metro), esc(pay_title),
                        PAY_START, pay_inner, PAY_END))
    filters_block = filters_block.replace(
        '<section id="payWrap" style="display:none;"><div class="paypanel" id="payPanel"></div></section>',
        baked_paywrap)

    h1 = "Find the Latest <em>%s</em> in Chicago" % esc(cfg["role"])
    intro = esc(cfg.get("hero_sub", ""))

    # ---- feed-computed content values (metro set = board.json, the honest sample) -------
    as_of = bake_date(feed_dir)
    pstats = pay_range_stats(metro_set)
    pay_n = pstats["n"] if pstats else 0
    pay_total = pstats["total"] if pstats else len(metro_set)
    role_rows = role_pay_rows(metro_set, WH_ROLE_DISPLAY)                 # [(label, openings, median)]
    role_median_by_label = {lbl: med for lbl, _cnt, med in role_rows}
    emp_rows, emp_unique, emp_top_share = employer_rows(
        metro_set, n=6, blocklist=WH_EMPLOYER_BLOCKLIST)
    n_open = len(feed_jobs)

    # Bake-time tokens so config prose/FAQ carries the page's OWN computed numbers and never
    # goes stale (content spec: "answer with the page's own computed numbers"). A token whose
    # value is unavailable resolves to an empty string; write config so that reads cleanly.
    def _m0(v):
        return "$%d" % int(round(v)) if v is not None else ""
    fk_med = role_median_by_label.get("Forklift operator")
    subst = {
        "{as_of}": as_of,
        "{open}": str(n_open),
        "{pay_n}": str(pay_n), "{pay_total}": str(pay_total),
        "{pay_median}": _m0(pstats["med"]) if pstats else "",
        "{pay_low}": _m0(pstats["lo"]) if pstats else "",
        "{pay_high}": _m0(pstats["hi"]) if pstats else "",
        "{forklift_median}": _m0(fk_med),
        "{employers}": str(emp_unique),
    }

    def fill(s):
        s = "" if s is None else str(s)
        for k, v in subst.items():
            s = s.replace(k, v)
        return s

    faqs = [(fill(q), fill(a)) for q, a in cfg.get("faqs", [])]

    # ---- section: pay by role (range bar itself is baked above in #payWrap) --------------
    pay_h2 = cfg.get("pay_content_h2", "What warehouse work pays in Chicago")
    default_lede = (
        "Hourly equivalent, computed from the %d of %d current Chicago warehouse listings "
        "that publish pay. Salaried roles convert at 2,080 hours.%s For reference, Chicago's "
        "minimum wage is $17.05 an hour and the Illinois state minimum is $15.00."
        % (pay_n, pay_total, (" As of %s." % as_of) if as_of else ""))
    pay_lede = fill(cfg.get("pay_lede", default_lede))
    role_table = render_dtable(
        ["Role", "Openings", "Median"],
        [(lbl, cnt, {"b": _money(med)}) for lbl, cnt, med in role_rows])
    pay_sec = ""
    if role_table or pay_lede:
        pay_sec = ('<section class="sec"><h2>%s</h2><p class="lede">%s</p>%s%s</section>'
                   % (esc(pay_h2), esc(pay_lede), role_table, fill(cfg.get("pay_extra", ""))))

    # ---- section: who is hiring ----------------------------------------------------------
    emp_sec = ""
    if emp_rows:
        emp_table = render_dtable(["Employer", "Open"],
                                  [(co, {"b": cnt}) for co, cnt in emp_rows])
        frag = ("Chicago warehouse hiring is spread across many employers. %d different "
                "companies have current openings here and no single one is more than %d%% of "
                "them, so applying to several places at once is normal and turning one offer "
                "down rarely closes the others." % (emp_unique, emp_top_share))
        emp_sec = ('<section class="sec"><h2>Who is hiring right now</h2>'
                   '<p class="lede">Employers with the most open warehouse roles on this board '
                   'today.</p>%s<p>%s</p></section>' % (emp_table, esc(frag)))

    # ---- section: getting hired (process ladder) -----------------------------------------
    hire_sec = ""
    hire_ladder = render_ladder([(s[0], s[1]) for s in cfg.get("hiring_steps", [])])
    if hire_ladder:
        hire_sec = ('<section class="sec"><h2>Getting hired</h2>'
                    '<p class="lede">What the process usually looks like from applying to your '
                    'first shift.</p>%s</section>' % hire_ladder)

    # ---- section: moving up (role ladder + certification economics) ----------------------
    # Ladder rows: [label, time]. Median pay is injected ONLY for roles the feed prices;
    # steps above the feed (lead, supervisor, ops) show "—" rather than an invented figure.
    move_sec = ""
    ladder_cfg = cfg.get("ladder", [])
    if ladder_cfg:
        lrows = []
        for label, tim in ladder_cfg:
            med = role_median_by_label.get(label)
            # Blank (not an em-dash: house style bans them) where the board does not price
            # the step; the section note explains the blanks.
            lrows.append((label, tim, {"b": _money(med)} if med is not None else ""))
        move_table = render_dtable(["Step", "Typical time", "Median"], lrows)
        move_sec = ('<section class="sec"><h2>Moving up</h2>'
                    '<p class="lede">Warehouse work has a clear ladder, and most of it is '
                    'learned on the job rather than in a classroom.</p>%s%s</section>'
                    % (move_table, fill(cfg.get("cert_body", ""))))

    # ---- prose sections (verified facts; per-hub differentiated via config) --------------
    shifts_sec = ('<section class="sec"><h2>Shifts, pay structure and benefits</h2>%s</section>'
                  % fill(cfg["shifts_body"])) if cfg.get("shifts_body") else ""
    work_sec = ('<section class="sec"><h2>What the work is actually like</h2>%s</section>'
                % fill(cfg["work_body"])) if cfg.get("work_body") else ""

    # ---- FAQ (also emitted as FAQPage in <head>) -----------------------------------------
    faq_sec = ('<section class="sec faq-sec"><h2>Common questions</h2>%s</section>'
               % render_faq(faqs)) if faqs else ""

    # ---- related hubs --------------------------------------------------------------------
    mesh = "".join('<a href="%s">%s</a>' % (esc(h), esc(l)) for h, _e, l in cfg.get("related_links", []))
    related_sec = ('<section class="sec"><h2>%s</h2><div class="related">%s</div></section>'
                   % (esc(cfg.get("related_h2", "More warehouse jobs in Chicago")), mesh)) if mesh else ""

    content_sections = "".join([pay_sec, emp_sec, hire_sec, move_sec, shifts_sec,
                                work_sec, faq_sec, related_sec])

    # Baked count is a no-JS fallback; bbj-board.js syncs #endCount to the live filtered
    # count on load so this rule and the board's own meta count always agree.
    endrule = ('<div class="hub-endrule"><span>End of '
               '<span id="endCount">%d</span> openings</span></div>' % n_open) if n_open else ""
    alert_h2 = cfg.get("alert_band_h2", 'Sign up for <em>job alerts</em>')
    alert_sub = esc(cfg.get("alert_band_sub",
                    "Get notified when new warehouse jobs open in Chicago."))
    alertband = (
        '<section class="hub-alertband"><div class="in">'
        '<h2>%s</h2><p>%s</p>'
        '<button class="abtn" type="button" onclick="openAlerts();return false;">Get alerts</button>'
        '<p class="afine">Free. Unsubscribe any time.</p>'
        '</div></section>' % (alert_h2, alert_sub))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(meta)}">
<link rel="canonical" href="{canonical}">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png">
<link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(meta)}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:description" content="{esc(meta)}">
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);}})(window,document,'script','dataLayer','{GTM_ID}');</script>
<script>!function(c,l,a,r,i,t,y){{c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y)}}(window,document,"clarity","script","{CLARITY}");</script>
<script async src="https://www.googletagmanager.com/gtag/js?id={ADS_ID}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{ADS_ID}');</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Barlow:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/css/bbj-board.css">
<script type="application/ld+json">{faqpage_jsonld(faqs)}</script>
{baked_schema}
<script type="application/ld+json">{breadcrumb_jsonld(cfg)}</script>
</head>
<body>
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={GTM_ID}" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<nav>
<a class="nav-logo" href="/">BlackBar<span>Jobs</span></a>
<a class="nav-cta" href="#" onclick="openAlerts();return false;">Get Alerts</a>
</nav>
<header class="board-hero">
<div class="board-hero-inner">
<div class="board-eyebrow">Chicago Warehouse Jobs</div>
<h1>{h1}</h1>
<p>{intro}</p>
</div>
</header>
<script>window.BBJ_BOARD_PRESET = {json.dumps(preset)};</script>
<script>window.BBJ_FEED_KEY="{feed_key}";</script>
{filters_block}
{endrule}
{alertband}

<!-- CONTENT: researched, feed-computed sections (all server-rendered — DG2) -->
<div class="hubc"><div class="in">
{content_sections}
</div></div>

<footer>
<div class="footer-links"><a href="/">Home</a><span> · </span><a href="/chicago">Chicago Jobs</a><span> · </span><a href="/job-board">All Jobs</a></div>
<div class="footer-logo">BlackBar<span>Jobs</span>.com</div>
<p>Warehouse and logistics job alerts across Chicago.</p>
<p><a href="/about">About</a> · <a href="https://www.termsfeed.com/live/e651a49f-d387-4d53-baa2-d069b9f9677f" target="_blank" rel="noopener">Terms &amp; Conditions</a> · <a href="https://www.termsfeed.com/live/e651a49f-d387-4d53-baa2-d069b9f9677f" target="_blank">Privacy Policy</a> · <a href="mailto:info@blackbarjobs.com">Contact</a></p>
</footer>
{modals_block}
<script src="/js/bbj-board.js" defer></script>
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<script src="/js/supabase-config.js"></script>
<script src="/js/bbj-auth-nav.js"></script>
<script src="/js/bbj-register-overlay.js"></script>
</body>
</html>"""


def main():
    ap = argparse.ArgumentParser(description="Build board-based warehouse hub pages")
    ap.add_argument("config")
    ap.add_argument("--feed-dir", default="feed")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--out-dir")
    args = ap.parse_args()

    cfgs = json.loads(Path(args.config).read_text(encoding="utf-8"))
    board_html = (REPO / "job-board.html").read_text(encoding="utf-8")

    results = gate.evaluate(cfgs, args.feed_dir)
    ok, _blocked = gate.print_report(results)

    base = Path(args.out_dir) if args.out_dir else REPO
    for r in ok:
        cfg = r["cfg"]
        html = build_hub(cfg, args.feed_dir, board_html)
        dest = base / cfg.get("path", cfg["slug"].lstrip("/") + ".html")
        if args.write:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(html, encoding="utf-8", newline="")
            print("  wrote %s  (%d bytes)" % (dest, len(html)))
        else:
            print("  built %s  (%d bytes, dry-run)" % (dest, len(html)))
    print("Done: %d hub(s)." % len(ok))


if __name__ == "__main__":
    main()
