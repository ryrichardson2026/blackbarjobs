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


HUB_CSS = """
  .hub-band{background:linear-gradient(135deg,#000814,#001D3D);color:#fff;padding:34px 20px 30px;}
  .hub-band-inner{max-width:1100px;margin:0 auto;}
  .hub-eyebrow{font-family:'Barlow Condensed',sans-serif;font-size:0.72rem;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#FFC300;margin-bottom:8px;}
  .hub-band h1{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:clamp(1.9rem,5vw,2.6rem);line-height:1.08;margin:0 0 8px;}
  .hub-band h1 em{color:#FFC300;font-style:normal;}
  .hub-band p{color:rgba(255,255,255,0.78);font-size:1rem;line-height:1.55;max-width:640px;margin:0;}
  .hub-section{max-width:1100px;margin:0 auto;padding:0 20px;}
  .hub-pay{background:#000814;padding:34px 0 38px;margin-top:8px;}
  .hub-pay h2,.hub-content h2{font-family:'Barlow Condensed',sans-serif;font-weight:800;letter-spacing:0.01em;}
  .hub-pay h2{color:#fff;font-size:1.6rem;margin:0 0 6px;}
  .hub-pay p.intro{color:rgba(255,255,255,0.6);font-size:0.92rem;margin:0 0 18px;max-width:640px;}
  .pay-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;max-width:640px;}
  .pay-card{background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.14);border-radius:12px;padding:16px 14px;}
  .pay-card-label{font-size:0.64rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(255,255,255,0.45);margin-bottom:8px;}
  .pay-card-rate{font-family:'Barlow Condensed',sans-serif;font-size:2rem;font-weight:800;color:#FFC300;line-height:1;}
  .pay-card-annual{font-size:0.72rem;}
  .hub-content{padding:36px 0 10px;}
  .hub-content h2{color:#001D3D;font-size:1.5rem;margin:0 0 14px;}
  .hub-content h3{font-family:'Barlow Condensed',sans-serif;font-weight:800;color:#001D3D;font-size:1.1rem;margin:22px 0 10px;}
  .hub-content p{color:#333;font-size:0.95rem;line-height:1.7;max-width:720px;margin:0 0 12px;}
  .hub-ul{list-style:none;padding:0;margin:0 0 8px;display:flex;flex-direction:column;gap:8px;max-width:720px;}
  .hub-ul li{display:flex;gap:10px;font-size:0.95rem;color:#333;line-height:1.5;}
  .hub-ul li::before{content:'';width:6px;height:6px;border-radius:50%;background:#FFC300;flex-shrink:0;margin-top:8px;}
  .hub-faq-q{font-family:'Barlow Condensed',sans-serif;font-weight:800;color:#001D3D;font-size:1.02rem;margin:18px 0 6px;}
  .hub-faq-a{color:#444;font-size:0.9rem;line-height:1.65;max-width:720px;margin:0;}
  .hub-mesh{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 4px;}
  .hub-mesh a{font-family:'Barlow Condensed',sans-serif;font-size:0.85rem;font-weight:700;color:#001D3D;background:#f7f8fa;border:1px solid #d0d5dd;border-radius:8px;padding:8px 14px;text-decoration:none;}
  .hub-mesh a:hover{border-color:#FFC300;}
"""


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

    # content-below sections
    reqs = "".join("<li>%s</li>" % esc(r) for r in cfg.get("requirements", []))
    duties = "".join("<li>%s</li>" % esc(d) for d in cfg.get("duties", []))
    faqs = cfg.get("faqs", [])
    faq_html = "".join('<div class="hub-faq-q">%s</div><p class="hub-faq-a">%s</p>' % (esc(q), esc(a))
                       for q, a in faqs)
    mesh = "".join('<a href="%s">%s %s</a>' % (esc(h), e, esc(l))
                   for h, e, l in cfg.get("related_links", []))

    role_body = cfg.get("role_body", "")
    demand_body = cfg.get("demand_body", "")

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
<style>{HUB_CSS}</style>
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
<header class="hub-band">
<div class="hub-band-inner">
<div class="hub-eyebrow">Chicago Warehouse Jobs</div>
<h1>{h1}</h1>
<p>{intro}</p>
</div>
</header>
<script>window.BBJ_BOARD_PRESET = {json.dumps(preset)};</script>
<script>window.BBJ_FEED_KEY="{feed_key}";</script>
{filters_block}

<!-- CONTENT: overview, requirements, FAQ, related -->
<div class="hub-content">
  <div class="hub-section">
    <h2>{esc(cfg.get("role", "Warehouse Jobs"))} in Chicago</h2>
    {demand_body}
    {role_body}
    <h3>What You Need</h3>
    <ul class="hub-ul">{reqs}</ul>
    <h3>Common Duties</h3>
    <ul class="hub-ul">{duties}</ul>
    <h3>Frequently Asked Questions</h3>
    {faq_html}
    <h3>More Warehouse Jobs in Chicago</h3>
    <div class="hub-mesh">{mesh}</div>
  </div>
</div>

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
