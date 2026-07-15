"""
BBJ Page Generator v5
- Matches Dallas template structure
- Alternating section backgrounds for visual rhythm
- Gold mid-CTA (primary conversion moment)
- navy-mid for requirements/schedules two-col-dark
- off-white alternating light sections
- Gold left-border accent on duty column in two-col

v5 CHANGES — Interlinking enforcement:
- validate_interlinking() runs on every page before output
- Warns when required link types are missing from related_links
- Enforces hub link, role hub link, DFW/market cross-link, training link rules
- See INTERLINKING RULES section below for full spec
"""

import json
import re
import sys
import warnings
from datetime import date
from pathlib import Path

# Reuse the feed baker's card renderers so baked-on-build cards stay BYTE-IDENTICAL
# to the live js/bbj-feed.js layer (single source of truth, no drift). bbj_feed_bake.py
# is a sibling at repo root; add this file's dir to sys.path so the import resolves no
# matter what cwd the external build driver runs from.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bbj_feed_bake import bake_page, BakeError

# Repo-root feed dir. Baked cards are read from feed/<BBJ_FEED_KEY>.json here.
FEED_DIR = Path(__file__).resolve().parent / "feed"

# ══════════════════════════════════════════════════════════════════
# NEW-PAGE BUILD ORDER (the "process" a new page must pass through)
# ══════════════════════════════════════════════════════════════════
# generate_page() now BAKES the job feed into the HTML on build (see the tail of
# generate_page + the bake hook), so a new page ships with real job cards in the
# raw HTML — provided feed/<key>.json already exists. Full order for a NEW page:
#
#   1. Add the target to automation/bbj_page_targets.json (key MUST byte-match the
#      page's BBJ_FEED_KEY). Use emit_target_entry(cfg) / upsert_target_entry(cfg)
#      below to avoid hand-editing errors.
#   2. Snapshot:  python automation/bbj_feed_snapshot.py --market <M> --out feed
#      -> writes feed/<key>.json.
#   3. generate_page(cfg) -> HTML with cards already baked (bake hook runs here).
#      If the feed does not exist yet, the container ships EMPTY and js/bbj-feed.js
#      fills it live; re-run after step 2 to bake.
#   4. Add the page's <loc> to sitemap.xml (bbj_feed_bake.py only BUMPS lastmod on
#      URLs already present; it does NOT add new URLs).
#   5. Audit: bbj_feed_target_check.py, bbj_link_audit.py, bbj_page_check.py.
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# INTERLINKING RULES
# ══════════════════════════════════════════════════════════════════
#
# Every page MUST link to its market hub. This is enforced.
# The related_links list + footer together must satisfy these rules.
#
# RULE 1 — Market hub link (REQUIRED)
#   Houston pages: /houston must appear in related_links or be the hub itself
#   DFW pages: /dallas must appear in related_links or be the hub
#
# RULE 2 — Cross-market link (REQUIRED for topic/role pages)
#   Houston topic pages must link to DFW equivalent (/dallas/...)
#   DFW topic pages must link to Houston equivalent (/houston/jobs/...)
#
# RULE 3 — Training schools link (REQUIRED for entry/licensing pages)
#   Pages with these slugs must include training schools in related_links:
#   no-experience, entry-level, level-2, level-3, how-to-become
#
# RULE 4 — Topic → suburb hub links (REQUIRED for topic pages)
#   Topic pages should link to at least 1 suburb hub where that topic is relevant
#   Suburb hub pages must link to at least 2 adjacent suburb hubs
#
# RULE 5 — Neighborhood → topic page links (REQUIRED for neighborhood pages)
#   Neighborhood pages must link to their primary topic page
#   (e.g. Medical Center → hospital security, Galleria → loss prevention)
#
# PAGE TYPE DETECTION — based on slug patterns:
#   hub:          slug == /houston or /dallas
#   role_hub:     slug contains unarmed|armed|event|overnight|loss-prevention|mobile-patrol|tsa
#   topic:        slug contains no-experience|full-time|entry-level|night-shift|part-time|level-2|level-3|airport|university|hospital|warehouse|hotel
#   suburb_hub:   slug matches /houston/jobs/[city]-security-jobs or /dallas/[city]-security-jobs
#   neighborhood: slug contains midtown|galleria|medical-center|montrose|heights|downtown|uptown|deep-ellum|design-district|medical-district
#   training:     slug contains training-schools
#
# ══════════════════════════════════════════════════════════════════

HOUSTON_HUB   = "/houston"
DFW_HUB       = "/dallas"
SA_HUB        = "/san-antonio"
AUSTIN_HUB    = "/austin"
TRAINING_HOU  = "/houston/jobs/security-training-schools-houston"
TRAINING_DFW  = "/dallas/security-training-schools-dfw"
TRAINING_SA   = "/san-antonio/jobs/security-training-schools-san-antonio"
TRAINING_AUS  = "/austin/jobs/security-training-schools-austin"

LICENSING_SLUGS = ["no-experience", "entry-level", "level-2", "level-3", "how-to-become"]
NEIGHBORHOOD_SLUGS = ["midtown", "galleria", "medical-center", "montrose", "heights",
                      "downtown-houston", "downtown-dallas", "uptown", "deep-ellum",
                      "design-district", "medical-district"]

def detect_page_type(slug):
    s = slug.lower()
    if s in [HOUSTON_HUB, DFW_HUB]: return "hub"
    if any(x in s for x in NEIGHBORHOOD_SLUGS): return "neighborhood"
    if "training-school" in s: return "training"
    if any(x in s for x in LICENSING_SLUGS): return "licensing"
    if any(x in s for x in ["unarmed","armed","event-security","overnight","loss-prevention","mobile-patrol","tsa-airport"]): return "role_hub"
    if any(x in s for x in ["full-time","night-shift","part-time","hospital-security","warehouse","hotel-security","airport-security","university-security","industrial-security","retail-security","school-security","corporate-campus","data-center"]): return "topic"
    if s.endswith("-security-jobs") or s.endswith("-jobs"): return "suburb_hub"
    return "other"

def validate_interlinking(cfg):
    """
    Validates interlinking rules and prints warnings for violations.
    Does not block page generation — warns so issues can be fixed.
    """
    slug    = cfg.get("slug", "")
    market  = cfg.get("market", "Houston")
    related = cfg.get("related_links", [])
    page_type = detect_page_type(slug)

    # Extract all hrefs from related_links
    hrefs = [r[0] for r in related]
    hrefs_str = " ".join(hrefs)

    issues = []

    # RULE 1: Market hub link
    hub_map = {"Houston": HOUSTON_HUB, "DFW": DFW_HUB, "San Antonio": SA_HUB, "Austin": AUSTIN_HUB, "Chicago": "/chicago"}
    hub = hub_map.get(market, DFW_HUB)
    if hub not in hrefs and slug != hub:
        issues.append(f"RULE 1: Missing market hub link ({hub}) in related_links")

    # RULE 2: Cross-market link (topic + role_hub pages)
    if page_type in ("topic", "role_hub"):
        cross_prefixes = {"Houston": ["/dallas/"], "DFW": ["/houston/jobs/"], "San Antonio": ["/dallas/", "/houston/jobs/"], "Austin": ["/dallas/", "/houston/jobs/"]}
        prefixes = cross_prefixes.get(market, ["/dallas/"])
        has_cross = any(any(h.startswith(p) for p in prefixes) for h in hrefs)
        if not has_cross:
            issues.append(f"RULE 2: No cross-market link (expected a link starting with one of {prefixes}) in related_links")

    # RULE 3: Training schools link for licensing pages
    if page_type == "licensing":
        training_map = {"Houston": TRAINING_HOU, "DFW": TRAINING_DFW, "San Antonio": TRAINING_SA, "Austin": TRAINING_AUS}
        training = training_map.get(market, TRAINING_DFW)
        if training not in hrefs:
            # Also accept the texas-wide training page
            if "training-school" not in hrefs_str and "security-license" not in hrefs_str:
                issues.append(f"RULE 3: Licensing page missing training schools link ({training})")

    # RULE 4a: Topic pages should link to at least 1 suburb hub
    if page_type == "topic":
        suburb_pattern = "-security-jobs" if market == "Houston" else "-security-jobs"
        has_suburb = any(suburb_pattern in h for h in hrefs)
        if not has_suburb:
            issues.append("RULE 4: Topic page has no suburb city hub link in related_links")

    # RULE 4b: Suburb hubs should link to at least 2 other suburb hubs
    if page_type == "suburb_hub":
        sibling_hubs = [h for h in hrefs if h.endswith("-security-jobs") and h != slug]
        if len(sibling_hubs) < 2:
            issues.append(f"RULE 4: Suburb hub links to only {len(sibling_hubs)} sibling hub(s) — need at least 2")

    # RULE 5: Neighborhood pages must link to a topic page
    if page_type == "neighborhood":
        topic_prefixes = ["/houston/jobs/hospital", "/houston/jobs/houston-bar", "/houston/jobs/loss-prevention",
                         "/houston/jobs/houston-retail", "/houston/jobs/overnight", "/houston/jobs/full-time",
                         "/dallas/hospital", "/dallas/dallas-bar", "/dallas/loss-prevention", "/dallas/overnight"]
        has_topic = any(any(h.startswith(p) for p in topic_prefixes) for h in hrefs)
        if not has_topic:
            issues.append("RULE 5: Neighborhood page missing link to primary topic page")

    if issues:
        page_name = slug.split("/")[-1]
        print(f"\n⚠️  INTERLINKING WARNINGS — {page_name}")
        for issue in issues:
            print(f"   → {issue}")
        print()

    return issues

TODAY     = date.today().isoformat()
BASE_URL  = "https://www.blackbarjobs.com"
GTM_ID    = "GTM-TP9JXK39"
CLARITY   = "wvxhs1xht1"
ADS_ID    = "AW-17039190320"
# WEBHOOK + ADS_CONV removed: registration webhook and the Ads conversion now
# fire only from the shared overlay's dataLayer events via GTM, never inline.

# Feed source = static per-page JSON snapshots under /feed/<key>.json, rendered
# by /js/bbj-feed.js. The old Google Sheets CSV feed (PUB_BASE + MASTER_* GIDs)
# has been retired. The per-page key is BBJ_FEED_KEY = slug without leading slash.

HOUSTON_FOOTER = [
    ("/houston",                                    "Houston Security Jobs"),
    ("/houston/jobs/security-officer-jobs-houston", "Security Officer Jobs"),
    ("/houston/jobs/armed-security-houston",        "Armed Security"),
    ("/houston/jobs/unarmed-security-houston",      "Unarmed Security"),
    ("/houston/jobs/overnight-security-houston",    "Overnight Security"),
    ("/houston/jobs/event-security-houston",        "Event Security"),
    ("/texas/texas-security-license-requirements",   "TX License Guide"),
]
DFW_FOOTER = [
    ("/dallas",                 "DFW Security Jobs"),
    ("/dallas/security-officer-jobs-dallas", "Dallas Security Jobs"),
    ("/dallas/armed-security-dfw",           "Armed Security"),
    ("/dallas/unarmed-security-dfw",         "Unarmed Security"),
    ("/dallas/overnight-security-dfw",       "Overnight Security"),
    ("/dallas/event-security-dfw",           "Event Security"),
    ("/texas/texas-security-license-requirements", "TX License Guide"),
]
HOUSTON_RESOURCES = [
    ("/houston",                                "Houston Security Jobs - Complete Guide"),
    ("/texas/how-to-become-a-security-guard-in-texas","How To Become A Security Officer in Texas"),
    ("/texas/security-guard-salary-texas",            "Texas Security Officer Salary Guide"),
    ("/texas/security-jobs-for-veterans-texas",       "Veterans Security Jobs in Texas"),
]
DFW_RESOURCES = [
    ("/dallas",                      "DFW Security Jobs - Complete Guide"),
    ("/texas/how-to-become-a-security-guard-in-texas","How To Become A Security Officer in Texas"),
    ("/texas/security-guard-salary-texas",            "Texas Security Officer Salary Guide"),
    ("/dallas/dallas-security-jobs-guide",             "Dallas Security Jobs Guide"),
    ("/texas/security-jobs-for-veterans-texas",       "Veterans Security Jobs in Texas"),
]


SA_FOOTER = [
    ("/san-antonio",                                       "San Antonio Security Jobs"),
    ("/san-antonio/jobs/unarmed-security-san-antonio",     "Unarmed Security"),
    ("/san-antonio/jobs/armed-security-san-antonio",       "Armed Security"),
    ("/san-antonio/jobs/event-security-san-antonio",       "Event Security"),
    ("/san-antonio/jobs/overnight-security-san-antonio",   "Overnight Security"),
    ("/san-antonio/jobs/hospital-security-san-antonio",    "Hospital Security"),
    ("/texas/texas-security-license-requirements",          "TX License Guide"),
]
SA_RESOURCES = [
    ("/san-antonio",                                       "San Antonio Security Jobs - Complete Guide"),
    ("/texas/how-to-become-a-security-guard-in-texas",           "How To Become A Security Officer in Texas"),
    ("/texas/security-guard-salary-texas",                       "Texas Security Officer Salary Guide"),
    ("/texas/security-jobs-for-veterans-texas",                  "Veterans Security Jobs in Texas"),
]
AUSTIN_FOOTER = [
    ("/austin",                                            "Austin Security Jobs"),
    ("/austin/jobs/unarmed-security-austin",               "Unarmed Security"),
    ("/austin/jobs/armed-security-austin",                 "Armed Security"),
    ("/austin/jobs/event-security-austin",                 "Event Security"),
    ("/austin/jobs/overnight-security-austin",             "Overnight Security"),
    ("/austin/jobs/hospital-security-austin",              "Hospital Security"),
    ("/texas/texas-security-license-requirements",          "TX License Guide"),
]
AUSTIN_RESOURCES = [
    ("/austin",                                            "Austin Security Jobs - Complete Guide"),
    ("/texas/how-to-become-a-security-guard-in-texas",           "How To Become A Security Officer in Texas"),
    ("/texas/security-guard-salary-texas",                       "Texas Security Officer Salary Guide"),
    ("/texas/security-jobs-for-veterans-texas",                  "Veterans Security Jobs in Texas"),
]

PAGE_CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --navy-deep: #000814;
    --navy-mid:  #001D3D;
    --navy-light:#003566;
    --gold:      #FFC300;
    --gold-hover:#FFD60A;
    --gold-muted:#E6A800;
    --white:     #ffffff;
    --off-white: #f4f5f7;
    --charcoal:  #1a1a1a;
    --muted:     #5a6474;
    --border:    #e2e5ea;
  }
  html { scroll-behavior: smooth; }
  body { font-family: 'Barlow', sans-serif; background: var(--white); color: var(--charcoal); font-size: 16px; line-height: 1.6; -webkit-font-smoothing: antialiased; }

  /* ── NAV ── */
  nav { position: fixed; top: 0; left: 0; right: 0; z-index: 200; background: var(--white); border-bottom: 1px solid var(--border); padding: 10px 20px; display: flex; align-items: center; justify-content: space-between; }
  .nav-logo { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: 1.25rem; letter-spacing: 0.02em; color: #111; line-height: 1; display: inline-block; text-decoration: none; }
  .logo-bb { border-bottom: 9px solid #111; padding-bottom: 3px; display: inline-block; line-height: 1; }
  .logo-gold { color: #FFC300; }

  /* ── HERO ── */
  .hero { margin-top: 49px; background: #1a1a1a; position: relative; overflow: hidden; min-height: calc(100vh - 49px); display: flex; flex-direction: column; }
  .hero::before { content: ''; position: absolute; inset: 0; background-image: linear-gradient(rgba(255,195,0,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,195,0,0.04) 1px, transparent 1px); background-size: 40px 40px; pointer-events: none; z-index: 0; }
  .hero-image-wrap { position: absolute; inset: 0; overflow: hidden; z-index: 0; }
  .hero-image-wrap img { width: 100%; height: 100%; object-fit: cover; object-position: center; filter: brightness(0.6) saturate(0.8); display: block; }
  .hero-image-overlay { position: absolute; inset: 0; background: linear-gradient(to bottom, rgba(0,8,20,0.2) 0%, rgba(0,8,20,0.75) 60%); }
  .hero-content { position: relative; z-index: 2; padding: 100px 20px 48px; flex: 1; display: flex; flex-direction: column; justify-content: flex-end; }
  .hero-badge { display: inline-block; font-family: 'Barlow Condensed', sans-serif; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--gold); border: 1px solid rgba(255,195,0,0.4); padding: 4px 10px; border-radius: 3px; margin-bottom: 14px; width: fit-content; }
  .hero h1 { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: clamp(2.4rem, 9vw, 3.2rem); line-height: 1.05; letter-spacing: -0.01em; color: var(--white); margin-bottom: 10px; }
  .hero h1 em { color: var(--gold); font-style: normal; }
  .hero-sub { font-size: 1rem; color: rgba(255,255,255,0.75); font-weight: 400; line-height: 1.55; max-width: 440px; margin-bottom: 24px; }
  .hero-ctas { display: flex; flex-direction: column; gap: 10px; max-width: 360px; }
  .btn-primary { display: block; width: 100%; padding: 15px; background: var(--gold); color: var(--navy-deep); font-family: 'Barlow Condensed', sans-serif; font-size: 1.1rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; border: none; border-radius: 10px; cursor: pointer; text-align: center; text-decoration: none; transition: background 0.15s; }
  .btn-primary:hover { background: var(--gold-hover); }
  .btn-navy { display: block; width: 100%; padding: 15px; background: var(--navy-deep); color: var(--gold); font-family: 'Barlow Condensed', sans-serif; font-size: 1.1rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; border: 2px solid rgba(255,195,0,0.4); border-radius: 10px; cursor: pointer; text-align: center; text-decoration: none; transition: border-color 0.15s; }
  .btn-navy:hover { border-color: var(--gold); }

  /* ── SECTION BASES ── */
  .section-white   { background: var(--white);     padding: 18px 0 0; }
  .section-offwhite{ background: var(--off-white);  padding: 18px 0 0; }
  .section-dark    { background: var(--navy-deep);  padding: 18px 0 0; }
  .section-mid     { background: var(--navy-mid);   padding: 18px 0 0; }

  /* divider lines adapt to background */
  .section-white    .section-divider::before,
  .section-white    .section-divider::after,
  .section-offwhite .section-divider::before,
  .section-offwhite .section-divider::after { background: var(--border); }
  .section-white    .section-divider span,
  .section-offwhite .section-divider span   { color: var(--gold-muted); }
  .section-dark  .section-divider::before,
  .section-dark  .section-divider::after,
  .section-mid   .section-divider::before,
  .section-mid   .section-divider::after    { background: rgba(255,255,255,0.12); }
  .section-dark  .section-divider span,
  .section-mid   .section-divider span      { color: var(--gold); }

  /* text colours */
  .section-white    .section-wrap h2,
  .section-offwhite .section-wrap h2 { color: var(--navy-deep); }
  .section-white    .section-wrap p,
  .section-offwhite .section-wrap p  { color: var(--charcoal); }
  .section-dark  .section-wrap h2,
  .section-mid   .section-wrap h2    { color: var(--white); }
  .section-dark  .section-wrap p,
  .section-mid   .section-wrap p     { color: rgba(255,255,255,0.72); }

  /* duty-list text */
  .section-white    .duty-list li,
  .section-offwhite .duty-list li    { color: var(--charcoal); }
  .section-dark  .duty-list li,
  .section-mid   .duty-list li       { color: rgba(255,255,255,0.82); }

  /* related-item */
  .section-dark .related-item,
  .section-mid  .related-item  { background: rgba(255,255,255,0.04); border-color: rgba(255,255,255,0.12); }
  .section-dark .related-item-label,
  .section-mid  .related-item-label { color: var(--white); }
  .section-dark .related-item-arrow,
  .section-mid  .related-item-arrow { color: rgba(255,255,255,0.35); }
  .section-dark .related-item:hover,
  .section-mid  .related-item:hover { border-color: var(--gold); }

  /* ── SECTION DIVIDER ── */
  .section-divider { display: flex; align-items: center; gap: 12px; padding: 0 20px; margin: 0 0 12px; }
  .section-divider::before, .section-divider::after { content: ''; flex: 1; height: 1px; }
  .section-divider span { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; white-space: nowrap; }

  /* ── SECTION WRAP ── */
  .section-wrap { padding: 0 20px 28px; }
  .section-wrap h2 { font-family: 'Barlow Condensed', sans-serif; font-size: clamp(1.6rem, 5vw, 2.1rem); font-weight: 800; line-height: 1.1; letter-spacing: -0.01em; margin-bottom: 16px; }
  .section-wrap p { font-size: 0.92rem; line-height: 1.65; margin-bottom: 12px; max-width: 640px; }

  /* ── TWO-COL LAYOUTS ── */
  .two-col-light { background: var(--white); padding-top: 18px; }
  .two-col-light .section-divider span { color: var(--gold-muted); }
  .two-col-dark  { background: var(--navy-mid); padding-top: 18px; }
  .two-col-dark .section-wrap h2 { color: var(--white); }
  .two-col-dark .section-wrap p  { color: rgba(255,255,255,0.6); }
  .two-col-dark .duty-list li    { color: rgba(255,255,255,0.82); }
  .two-col-dark .section-divider span { color: var(--gold); }
  .two-col-dark .section-divider::before,
  .two-col-dark .section-divider::after { background: rgba(255,255,255,0.12); }

  /* Gold accent on duties column */
  .duties-col { border-left: 3px solid var(--gold); }

  /* ── PAY GRID ── */
  .pay-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 4px; }
  .pay-card { background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.14); border-radius: 12px; padding: 18px 16px; }
  .pay-card-label { font-size: 0.65rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: rgba(255,255,255,0.45); margin-bottom: 8px; }
  .pay-card-rate { font-family: 'Barlow Condensed', sans-serif; font-size: 2.1rem; font-weight: 800; color: var(--gold); line-height: 1; }
  .pay-card-annual { font-size: 0.72rem; color: rgba(255,195,0,0.7); margin-top: 5px; }

  /* ── DUTY LIST ── */
  .duty-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 9px; }
  .duty-list li { display: flex; align-items: flex-start; gap: 10px; font-size: 0.92rem; line-height: 1.5; }
  .duty-list li::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--gold); flex-shrink: 0; margin-top: 7px; }

  /* ── RELATED GRID ── */
  .related-grid { display: flex; flex-direction: column; gap: 8px; }
  .related-item { display: flex; align-items: center; justify-content: space-between; padding: 13px 16px; border: 1.5px solid; border-radius: 10px; text-decoration: none; transition: border-color 0.12s; }
  .related-item-label { font-family: 'Barlow Condensed', sans-serif; font-size: 1rem; font-weight: 700; }
  .related-item-arrow { font-size: 0.85rem; }

  /* ── RESOURCE LINKS ── */
  .link-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
  .link-list li a { font-size: 0.9rem; color: var(--navy-deep); text-decoration: underline; }

  /* ── FAQ ── */
  .faq-list { display: flex; flex-direction: column; border-top: 1px solid var(--border); }
  .faq-item { border-bottom: 1px solid var(--border); }
  .faq-q { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 0; cursor: pointer; font-family: 'Barlow Condensed', sans-serif; font-size: 1rem; font-weight: 700; color: var(--navy-deep); line-height: 1.3; user-select: none; }
  .faq-q .faq-icon { flex-shrink: 0; font-size: 1.1rem; color: var(--gold); transition: transform 0.18s; }
  .faq-item.open .faq-icon { transform: rotate(45deg); }
  .faq-a { display: none; padding: 0 0 14px; font-size: 0.88rem; color: var(--muted); line-height: 1.65; max-width: 580px; }
  .faq-item.open .faq-a { display: block; }

  /* ── GOLD MID-CTA ── */
  .mid-cta-gold { background: var(--gold); padding: 32px 20px; text-align: center; }
  .mid-cta-gold p { color: var(--navy-deep); font-size: 1rem; font-weight: 600; line-height: 1.5; margin-bottom: 18px; max-width: 540px; margin-left: auto; margin-right: auto; }
  .btn-cta-navy { display: inline-block; padding: 15px 32px; background: var(--navy-deep); color: var(--gold); font-family: 'Barlow Condensed', sans-serif; font-size: 1.1rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; border-radius: 10px; text-decoration: none; transition: background 0.15s; max-width: 300px; width: 100%; text-align: center; }
  .btn-cta-navy:hover { background: var(--navy-mid); }

  /* ── LIVE FEED ── */
  .jf-row { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--border); cursor: pointer; }
  .jf-row:last-child { border-bottom: none; }
  .jf-body { flex: 1; min-width: 0; }
  .jf-title { font-family: 'Barlow Condensed', sans-serif; font-size: 0.95rem; font-weight: 800; color: var(--navy-deep); line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .jf-meta { display: flex; align-items: center; gap: 0; margin-top: 2px; font-size: 0.7rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .jf-company { font-weight: 600; color: var(--charcoal); }
  .jf-sep { margin: 0 5px; color: #d0d5dd; }
  .jf-pay { font-size: 0.65rem; font-weight: 700; color: #1a6b2e; background: #e6f4eb; padding: 1px 5px; border-radius: 3px; margin-left: 6px; flex-shrink: 0; }
  .jf-apply { flex-shrink: 0; padding: 6px 12px; background: var(--navy-deep); color: var(--gold); font-family: 'Barlow Condensed', sans-serif; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase; border-radius: 4px; text-decoration: none; transition: background 0.12s; }
  .jf-apply:hover { background: var(--navy-light); }

  /* ── ALERT ── */
  .alert-wrap { background: var(--navy-deep); padding: 36px 20px 40px; text-align: center; border-top: 3px solid rgba(255,195,0,0.35); }
  .alert-wrap h2 { font-family: 'Barlow Condensed', sans-serif; font-size: clamp(1.6rem, 6vw, 2.2rem); font-weight: 800; color: var(--white); line-height: 1.1; margin-bottom: 6px; }
  .alert-wrap h2 span { color: var(--gold); }
  .alert-wrap > p { font-size: 0.88rem; color: rgba(255,255,255,0.55); margin-bottom: 20px; }
  .alert-form { display: flex; flex-direction: column; gap: 9px; max-width: 360px; margin: 0 auto; }
  .alert-field { position: relative; }
  .alert-field-icon { position: absolute; left: 14px; top: 50%; transform: translateY(-50%); font-size: 1rem; pointer-events: none; line-height: 1; }
  .alert-form input { width: 100%; padding: 13px 14px 13px 40px; border: 1.5px solid rgba(255,255,255,0.15); border-radius: 10px; font-size: 1rem; font-family: 'Barlow', sans-serif; color: var(--white); background: rgba(255,255,255,0.08); outline: none; transition: border-color 0.15s; -webkit-appearance: none; }
  .alert-form input::placeholder { color: rgba(255,255,255,0.35); }
  .alert-form input:focus { border-color: var(--gold); }
  .alert-trust { display: flex; align-items: center; gap: 6px; justify-content: center; margin-top: 8px; font-size: 0.7rem; color: rgba(255,255,255,0.35); font-weight: 500; }
  .alert-note { font-size: 0.62rem; color: rgba(255,255,255,0.25); line-height: 1.5; margin-top: 10px; max-width: 340px; margin-left: auto; margin-right: auto; }

  /* ── FOOTER ── */
  footer { padding: 22px 20px; text-align: center; background: var(--navy-deep); border-top: 1px solid rgba(255,255,255,0.08); }
  .footer-logo { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: 1.1rem; color: var(--white); margin-bottom: 6px; }
  .footer-logo span { color: var(--gold-muted); }
  footer p { font-size: 0.72rem; color: rgba(255,255,255,0.35); line-height: 1.6; }
  footer a { color: rgba(255,255,255,0.35); text-decoration: underline; }
  .footer-links { margin-bottom: 10px; display: flex; flex-wrap: wrap; justify-content: center; gap: 4px 2px; font-size: 0.72rem; }
  .footer-links a { color: rgba(255,255,255,0.45); text-decoration: none; }
  .footer-links a:hover { text-decoration: underline; color: var(--gold); }
  .footer-links span { color: rgba(255,255,255,0.18); }

  /* ── STICKY BAR ── */
  .sticky-bar { display:none; position:fixed; bottom:0; left:0; right:0; z-index:99; padding:10px 16px 16px; background:#000814; border-top:2px solid rgba(255,195,0,0.35); box-shadow:0 -4px 20px rgba(0,0,0,0.5); }
  .sticky-bar.show { display:block; }
  .sticky-bar a { display:flex; align-items:center; justify-content:center; width:100%; padding:14px; background:#FFC300; color:#000814; font-family:'Barlow Condensed',sans-serif; font-size:1.1rem; font-weight:800; letter-spacing:0.06em; text-transform:uppercase; border-radius:10px; text-decoration:none; }

  /* ── RESPONSIVE ── */
  @media (min-width: 640px) {
    .hero { min-height: 520px; max-height: 580px; height: 62vh; }
    .hero-content { padding: 0 48px 52px; justify-content: center; }
    .hero h1 { font-size: clamp(2.8rem, 4vw, 3.8rem); }
    .hero-ctas { max-width: 420px; }
    .section-wrap { padding: 0 40px 32px; }
    .section-divider { padding: 0 40px; margin: 0 0 14px; }
    .pay-grid { grid-template-columns: repeat(3, 1fr); }
    .alert-wrap { padding: 52px 40px 56px; }
    footer { padding: 28px 40px; }
    .mid-cta-gold { padding: 40px 40px; }
    .mid-cta-gold .btn-cta-navy { max-width: 280px; }
    .two-col-inner { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
    .two-col-inner .section-wrap { padding: 0 40px 32px; }
    .two-col-inner .section-wrap:first-child { padding-left: 40px; padding-right: 28px; border-right: 1px solid var(--border); }
    .two-col-inner .section-wrap:last-child { padding-left: 28px; padding-right: 40px; }
    .two-col-dark .two-col-inner .section-wrap:first-child { border-right-color: rgba(255,255,255,0.1); }
    .duties-col { border-left: none; border-top: 3px solid var(--gold); padding-top: 20px !important; }
    @media(max-width:639px){ body { padding-bottom: 74px; } }
    @media(min-width:640px){ .sticky-bar { display:none!important; } }
  }

  /* === BBJ Live Feed (hero-embedded) === */
  .form-card{background:var(--white);border-radius:16px;padding:16px;box-shadow:0 8px 40px rgba(0,0,0,0.35);}
  .form-card-title{font-family:'Barlow Condensed',sans-serif;font-size:1.05rem;font-weight:700;color:var(--navy-deep);letter-spacing:0.02em;margin-bottom:10px;text-transform:uppercase;}
  .hero-feed{display:flex;flex-direction:column;margin-bottom:12px;border-top:2px solid var(--navy-deep);border-bottom:1px solid #c8cdd4;}
  .hf-row{display:flex;align-items:flex-start;gap:10px;padding:5px 0;border-bottom:1px solid #e2e5ea;background: transparent; cursor: pointer;}
  .hf-row:last-child{border-bottom:none;}
  .hf-body{flex:1;min-width:0;}
  .hf-title{font-family:'Barlow Condensed',sans-serif;font-size:0.95rem;font-weight:800;color:var(--navy-deep);line-height:1.15;letter-spacing:0.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .hf-meta{display:flex;align-items:center;gap:0;margin-top:1px;flex-wrap:nowrap;font-size:0.68rem;color:var(--muted);font-family:'Barlow',sans-serif;font-weight:400;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .hf-apply{flex-shrink:0;align-self:center;padding:5px 11px;background:var(--navy-deep);color:var(--gold);font-family:'Barlow Condensed',sans-serif;font-size:0.72rem;font-weight:800;letter-spacing:0.06em;text-transform:uppercase;border:1.5px solid var(--navy-deep);border-radius:2px;cursor:pointer;text-decoration:none;display:inline-block;transition:background 0.12s,color 0.12s;white-space:nowrap;}
  .hf-apply:hover{background:var(--navy-light);border-color:var(--navy-light);}
  .hf-error{font-size:0.75rem;color:var(--muted);padding:10px 0;text-align:center;}
  .skeleton-row{display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #e2e5ea;}
  .skeleton-row:last-child{border-bottom:none;}
  .skeleton-body{flex:1;min-width:0;}
  .skeleton-line{background:linear-gradient(90deg,#f0f0f0 25%,#e0e0e0 50%,#f0f0f0 75%);background-size:200% 100%;animation:shimmer 1.4s infinite;border-radius:4px;}
  .skeleton-title{height:13px;width:75%;margin-bottom:6px;}
  .skeleton-meta{height:10px;width:50%;}
  .skeleton-btn{width:46px;height:28px;border-radius:8px;flex-shrink:0;}
  @keyframes shimmer{0%{background-position:200% 0;}100%{background-position:-200% 0;}}

/* -- MOBILE: hide hero image, collapse height -- */
@media (max-width: 639px) {
  .hero-img-wrap, .hero-image-wrap { display: none !important; }
  .hero { min-height: 0 !important; background: #000814 !important; }
}

/* -- MODERN HERO-EMBEDDED FEED -- */
.hero-content { padding: 90px 16px 24px; justify-content: flex-start; }
.hero-text-col { display: flex; flex-direction: column; }
.hero-stat-row { display: none; }
.form-card { background: var(--white); border-radius: 16px; padding: 16px; box-shadow: 0 8px 40px rgba(0,0,0,0.35); margin-top: 18px; }
.form-card-title { font-family:'Barlow Condensed',sans-serif; font-size:1.05rem; font-weight:700; color:var(--navy-deep); letter-spacing:0.02em; margin-bottom:10px; text-transform:uppercase; }
.hero-feed { display:flex; flex-direction:column; margin-bottom:12px; border-top:2px solid var(--navy-deep); border-bottom:1px solid #c8cdd4; }
.hf-row { display:flex; align-items:flex-start; gap:10px; padding:5px 0; border-bottom:1px solid #e2e5ea; background:transparent; }
.hf-row:last-child { border-bottom:none; }
.hf-body { flex:1; min-width:0; }
.hf-title { font-family:'Barlow Condensed',sans-serif; font-size:0.95rem; font-weight:800; color:var(--navy-deep); line-height:1.15; letter-spacing:0.01em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.hf-meta { display:flex; align-items:center; gap:0; margin-top:1px; flex-wrap:nowrap; font-size:0.68rem; color:var(--muted); font-family:'Barlow',sans-serif; font-weight:400; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.hf-company { font-weight:600; color:var(--charcoal); }
.hf-sep { margin:0 4px; color:#c8cdd4; }
.hf-location { color:var(--muted); }
.hf-tag { display:inline-block; font-size:0.6rem; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; color:var(--muted); border:1px solid #c8cdd4; padding:1px 4px; border-radius:2px; margin-left:5px; white-space:nowrap; flex-shrink:0; }
.hf-apply { flex-shrink:0; align-self:center; padding:5px 11px; background:var(--navy-deep); color:var(--gold); font-family:'Barlow Condensed',sans-serif; font-size:0.72rem; font-weight:800; letter-spacing:0.06em; text-transform:uppercase; border:1.5px solid var(--navy-deep); border-radius:2px; cursor:pointer; text-decoration:none; display:inline-block; transition:background 0.12s,color 0.12s; white-space:nowrap; }
.hf-apply:hover { background:var(--navy-light); border-color:var(--navy-light); }
.hf-loading { text-align:center; padding:16px 0; font-size:0.8rem; color:var(--muted); font-weight:500; }
.hf-error { font-size:0.75rem; color:var(--muted); padding:10px 0; text-align:center; }
@media (min-width: 640px) {
  .hero-content { display:grid; grid-template-columns:1fr 420px; align-items:center; gap:48px; max-width:1200px; margin:0 auto; padding:0 48px; justify-content:initial; }
  .hero-text-col { justify-content:center; }
  .hero h1 { text-align:left; }
  .hero-image-overlay { background: linear-gradient(105deg, rgba(0,8,20,0.82) 0%, rgba(0,8,20,0.55) 45%, rgba(0,8,20,0.25) 100%); }
  .hero .hero-sub { text-align:left; font-size:1.1rem; max-width:420px; margin-bottom:0; }
  .hero-stat-row { display:flex; gap:32px; margin-top:32px; }
  .hero-stat { display:flex; flex-direction:column; gap:2px; }
  .hero-stat-num { font-family:'Barlow Condensed',sans-serif; font-size:1.8rem; font-weight:800; color:var(--gold); line-height:1; }
  .hero-stat-label { font-size:0.72rem; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:rgba(255,255,255,0.45); }
  .form-card { max-width:420px; width:100%; border-radius:20px; padding:28px 24px 22px; background:rgba(255,255,255,0.97); box-shadow:0 24px 64px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.08); margin-top:0; }
}
"""

# ── Schema ────────────────────────────────────────────────────────
def faq_schema(faqs):
    return json.dumps({"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
        {"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}}
        for q,a in faqs]}, indent=2)

def jobposting_schema(cfg):
    return json.dumps({"@context":"https://schema.org/","@type":"JobPosting",
        "title":cfg["role"],"description":cfg["meta_desc"],
        "identifier":{"@type":"PropertyValue","name":"BlackBarJobs","value":cfg["slug"].strip("/").replace("/","-")},
        # FLAG: datePosted/validThrough is a stale-date pattern (build date + end-of-year).
        # Revisit alongside the Google-for-Jobs JobPosting schema work before relying on it.
        "datePosted":TODAY,"validThrough":f"{date.today().year}-12-31",
        "employmentType":cfg.get("employment_type","FULL_TIME"),
        "hiringOrganization":{"@type":"Organization","name":"BlackBarJobs","sameAs":BASE_URL},
        "jobLocation":{"@type":"Place","address":{"@type":"PostalAddress",
            "addressLocality":cfg["city"],"addressRegion":cfg.get("region","TX"),"addressCountry":"US"}},
        "baseSalary":{"@type":"MonetaryAmount","currency":"USD","value":{
            "@type":"QuantitativeValue","minValue":cfg.get("pay_min",15),
            "maxValue":cfg.get("pay_max",22),"unitText":"HOUR"}},
        "url":f"{BASE_URL}{cfg['slug']}"}, indent=2)

def collection_schema(cfg):
    # Hub/directory pages: an ItemList of the metro pages, not a single JobPosting.
    items = [{"@type":"ListItem","position":i+1,"name":label,"url":f"{BASE_URL}{href}"}
             for i,(href,_emoji,label) in enumerate(cfg["related_links"])]
    return json.dumps({"@context":"https://schema.org","@type":"CollectionPage",
        "name":cfg["role"],"description":cfg["meta_desc"],"url":f"{BASE_URL}{cfg['slug']}",
        "mainEntity":{"@type":"ItemList","itemListElement":items}}, indent=2)

def breadcrumb_schema(cfg):
    market = cfg.get("market","Houston")
    if cfg.get("hub_mode"):
        return json.dumps({"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
            {"@type":"ListItem","position":1,"name":"BlackBarJobs","item":BASE_URL},
            {"@type":"ListItem","position":2,"name":cfg["role"],"item":f"{BASE_URL}{cfg['slug']}"}
        ]}, indent=2)
    hub_slug_map = {"Houston": "/houston", "DFW": "/dallas", "San Antonio": "/san-antonio", "Austin": "/austin", "Chicago": "/chicago"}
    hub_name_map = {"Houston": "Houston Security Jobs", "DFW": "DFW Security Jobs", "San Antonio": "San Antonio Security Jobs", "Austin": "Austin Security Jobs", "Chicago": "Chicago Security Jobs"}
    hub_slug = hub_slug_map.get(market, "/dallas")
    hub_name = hub_name_map.get(market, "DFW Security Jobs")
    return json.dumps({"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
        {"@type":"ListItem","position":1,"name":"BlackBarJobs","item":BASE_URL},
        {"@type":"ListItem","position":2,"name":hub_name,"item":f"{BASE_URL}{hub_slug}"},
        {"@type":"ListItem","position":3,"name":cfg["role"],"item":f"{BASE_URL}{cfg['slug']}"}
    ]}, indent=2)

# ── Feed ──────────────────────────────────────────────────────────
# The feed is rendered by the shared /js/bbj-feed.js, which reads the static
# snapshot at /feed/<BBJ_FEED_KEY>.json and populates #jobRows. The visible-job
# cap and the apply gating live in that shared script, not inline here.

# ── Builders ──────────────────────────────────────────────────────
def duty_list(items):
    return '<ul class="duty-list">\n' + '\n'.join(f'<li>{i}</li>' for i in items) + '\n</ul>'

def pay_grid(entry, exp, lead):
    def card(label, rate, annual):
        return f'<div class="pay-card"><div class="pay-card-label">{label}</div><div class="pay-card-rate">{rate}</div><div class="pay-card-annual">{annual}</div></div>'
    return f'<div class="pay-grid">{card("Entry Level",entry[0],entry[1])}{card("Experienced",exp[0],exp[1])}{card("Lead / Senior",lead[0],lead[1])}</div>'

def related_grid(links):
    items = '\n'.join(
        f'<a class="related-item" href="{href}"><span class="related-item-label">{emoji} {label}</span><span class="related-item-arrow">→</span></a>'
        for href,emoji,label in links)
    return f'<div class="related-grid">{items}</div>'

def footer_html(links):
    parts = []
    for i,(href,label) in enumerate(links):
        parts.append(f'<a href="{href}">{label}</a>')
        if i < len(links)-1: parts.append('<span>·</span>')
    return '\n'.join(parts)

def resource_list(links):
    lis = '\n'.join(f'<li><a href="{href}">{label}</a></li>' for href,label in links)
    return f'<ul class="link-list" style="margin:0;">\n{lis}\n</ul>'

def sec_div(label, mt0=False):
    style = ' style="margin-top:0;"' if mt0 else ''
    return f'<div class="section-divider"{style}><span>{label}</span></div>'

# ── Output guardrails (bake in fixes for past bugs) ────────────────
_A_HREF_RE  = re.compile(r'<a\b[^>]*?href="([^"]*)"', re.I)
_FAVICONS   = ('/favicon.ico', '/favicon-96.png', '/favicon-192.png', '/apple-touch-icon.png')

def _is_internal_href(href):
    h = href.strip().lower()
    if h.startswith(("mailto:", "tel:", "javascript:", "#", "data:", "//")):
        return False
    if h.startswith(("http://", "https://")):
        return "blackbarjobs.com" in h   # our own absolute URLs count as internal
    return True                          # site-relative

def assert_output_guardrails(html, slug):
    """Fail the build if a regressed past-bug pattern slips into a generated page."""
    # Guardrail A — no internal <a href> may carry a utm_ parameter.
    for href in _A_HREF_RE.findall(html):
        if _is_internal_href(href) and "utm_" in href.lower():
            raise SystemExit(f"BUILD BLOCKED — {slug}: internal link carries a UTM param: {href}")
    # Guardrail B — the favicon set must be emitted on every page.
    missing = [f for f in _FAVICONS if f not in html]
    if missing:
        raise SystemExit(f"BUILD BLOCKED — {slug}: missing favicon tag(s): {', '.join(missing)}")

# ── Main generator ────────────────────────────────────────────────
def generate_page(cfg):
    market      = cfg.get("market","Houston")
    city        = cfg["city"]
    role        = cfg["role"]
    slug        = cfg["slug"]
    title       = cfg["title"]
    meta_desc   = cfg["meta_desc"]
    canonical   = f"{BASE_URL}{slug}"
    region      = cfg.get("region","TX")
    hero_img    = cfg.get("hero_img","/images/overnight-security-hero.jpg")
    hero_alt    = cfg.get("hero_alt", f"{role} jobs {city} {region}")
    browse_url  = cfg.get("browse_url","/job-board")
    alert_city  = cfg.get("alert_city", city)
    # Hero-embedded feed tokens (golden template)
    metro_display   = cfg.get("metro_display", city)          # H1 city label, e.g. "Dallas-Fort Worth"
    metro_abbr      = cfg.get("metro_abbr", city)             # hero stat label, e.g. "DFW"
    feed_card_title = cfg.get("feed_card_title", f"Recent {role} Openings")
    # H1: default golden format, or a per-page override (e.g. trailing "No Experience Required" qualifier)
    h1_html = cfg.get("h1_override") or ('Find the Latest <em>' + cfg["h1_em"] + '</em> in ' + metro_display)

    # Feed key = slug without leading slash (e.g. "austin/jobs/armed-security-austin").
    # bbj-feed.js fetches /feed/<feed_key>.json; the overlay derives the metro from it too.
    feed_key  = cfg.get("feed_key", slug.lstrip("/"))
    res_map = {"Houston": HOUSTON_RESOURCES, "DFW": DFW_RESOURCES, "San Antonio": SA_RESOURCES, "Austin": AUSTIN_RESOURCES}
    ft_map  = {"Houston": HOUSTON_FOOTER,    "DFW": DFW_FOOTER,    "San Antonio": SA_FOOTER,    "Austin": AUSTIN_FOOTER}
    resources = cfg.get("resources", res_map.get(market, DFW_RESOURCES))
    ftlinks   = footer_html(cfg.get("footer_links", ft_map.get(market, DFW_FOOTER)))

    faqs        = cfg["faqs"]
    demand_h2   = cfg["demand_h2"]
    demand_body = cfg["demand_body"]
    role_h2     = cfg["role_h2"]
    role_body   = cfg["role_body"]
    duties      = cfg["duties"]
    pay_intro   = cfg["pay_intro"]
    pay_entry   = cfg["pay_entry"]
    pay_exp     = cfg["pay_exp"]
    pay_lead    = cfg["pay_lead"]
    mid_cta     = cfg["mid_cta_text"]
    requirements= cfg["requirements"]
    schedules   = cfg["schedules"]
    related     = cfg["related_links"]

    # ── Hub-mode overrides (national/directory pages); default to metro behavior ──
    badge       = cfg.get("badge_override", f"{city}, {region}")
    related_h2  = cfg.get("related_h2", f"More Security Jobs in {city}")
    browse_label= cfg.get("browse_label", f"All {city} Security Jobs")
    page_schema = collection_schema(cfg) if cfg.get("hub_mode") else jobposting_schema(cfg)

    # ── Interlinking validation ────────────────────────────────
    _issues = validate_interlinking(cfg)
    if _issues and not cfg.get("skip_interlink_gate"):
        raise SystemExit(
            "BUILD BLOCKED — " + slug + " fails interlinking rules:\n  - "
            + "\n  - ".join(_issues)
            + "\n  Fix related_links so the page joins the mesh, "
            + "or set skip_interlink_gate=True in this page's cfg to consciously override."
        )

    faq_html = '\n'.join(
        f'<div class="faq-item"><div class="faq-q" onclick="toggleFaq(this)">{q}<span class="faq-icon">+</span></div><div class="faq-a">{a}</div></div>'
        for q,a in faqs)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{meta_desc}">
<link rel="canonical" href="{canonical}">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png">
<link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:description" content="{meta_desc}">
<!-- GTM -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);}})(window,document,'script','dataLayer','{GTM_ID}');</script>
<!-- Clarity -->
<script>!function(c,l,a,r,i,t,y){{c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y)}}(window,document,"clarity","script","{CLARITY}");</script>
<!-- Ads -->
<script async src="https://www.googletagmanager.com/gtag/js?id={ADS_ID}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{ADS_ID}');</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Barlow:wght@400;500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">{faq_schema(faqs)}</script>
<script type="application/ld+json">{page_schema}</script>
<script type="application/ld+json">{breadcrumb_schema(cfg)}</script>
<style>{PAGE_CSS}</style>
</head>
<body>
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={GTM_ID}" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>

<div class="sticky-bar" id="stickyBar"><a href="#" onclick="bbjAlertOpen();return false;">Get Security Job Alerts</a></div>

<nav>
  <a class="nav-logo" href="/"><span class="logo-bb">BlackBar<span class="logo-gold">Jobs</span></span></a>
</nav>

<!-- HERO (hero-embedded feed) -->
<section class="hero" id="heroAnchor">
  <div class="hero-image-wrap">
    <img src="{hero_img}" alt="{hero_alt}" loading="eager">
    <div class="hero-image-overlay"></div>
  </div>
  <div class="hero-content">
    <div class="hero-text-col">
      <div class="hero-badge">{badge}</div>
      <h1>{h1_html}</h1>
      <p class="hero-sub">{cfg["hero_sub"]}</p>
      <div class="hero-stat-row">
        <div class="hero-stat"><span class="hero-stat-num">Live</span><span class="hero-stat-label">Updated Feed</span></div>
        <div class="hero-stat"><span class="hero-stat-num">{metro_abbr}</span><span class="hero-stat-label">Metro Coverage</span></div>
        <div class="hero-stat"><span class="hero-stat-num">Free</span><span class="hero-stat-label">Job Alerts</span></div>
      </div>
    </div>
    <div class="form-card" id="signup">
      <div class="form-card-title" style="text-align:center;letter-spacing:0.04em;">{feed_card_title}</div>
      <div class="hero-feed" id="indexJobFeed"></div>
      <a href="#" onclick="bbjAccOpen();return false;" class="btn-primary" style="display:block;width:100%;text-align:center;margin-top:10px;">See More Jobs →</a>
    </div>
  </div>
</section>

<!-- FAQ - white -->
<div class="section-white">
  {sec_div("FAQ", mt0=True)}
  <div class="section-wrap">
    <h2>Frequently Asked Questions</h2>
    <div class="faq-list">{faq_html}</div>
  </div>
</div>

<!-- DEMAND OVERVIEW - off-white -->
<div class="section-offwhite">
  {sec_div("Overview")}
  <div class="section-wrap">
    <h2>{demand_h2}</h2>
    {demand_body}
  </div>
</div>

<!-- ROLE OVERVIEW + DUTIES - white two-col -->
<div class="two-col-light">
  <div class="two-col-inner">
    <div class="section-wrap">
      {sec_div("Role Overview")}
      <h2>{role_h2}</h2>
      {role_body}
    </div>
    <div class="section-wrap duties-col">
      {sec_div("Duties")}
      <h2>Common Duties &amp; Responsibilities</h2>
      {duty_list(duties)}
    </div>
  </div>
</div>

<!-- PAY - navy-deep dark -->
<div class="section-dark">
  {sec_div("Compensation")}
  <div class="section-wrap">
    <h2>Typical Pay in {city}, {region}</h2>
    <p style="color:rgba(255,255,255,0.5);margin-bottom:20px;">{pay_intro}</p>
    {pay_grid(pay_entry, pay_exp, pay_lead)}
  </div>
</div>

<!-- MID CTA - GOLD -->
<div class="mid-cta-gold">
  <p>{mid_cta}</p>
  <a class="btn-cta-navy" href="{browse_url}">Browse All Jobs →</a>
</div>

<!-- REQUIREMENTS + SCHEDULES - navy-mid two-col-dark -->
<div class="two-col-dark">
  <div class="two-col-inner">
    <div class="section-wrap">
      {sec_div("Requirements")}
      <h2>What You Need</h2>
      {duty_list(requirements)}
    </div>
    <div class="section-wrap">
      {sec_div("Schedules")}
      <h2>Typical Schedules &amp; Environments</h2>
      {duty_list(schedules)}
    </div>
  </div>
</div>

<!-- RELATED - navy-deep dark -->
<div class="section-dark">
  {sec_div("Related Roles")}
  <div class="section-wrap">
    <h2>{related_h2}</h2>
    {related_grid(related)}
  </div>
</div>

<!-- RESOURCES - off-white -->
<div class="section-offwhite" id="resource-links">
  {sec_div("Guides &amp; Resources")}
  <div class="section-wrap">
    {resource_list(resources)}
    <a class="btn-primary" href="{browse_url}" style="display:inline-block;margin-top:18px;max-width:320px;text-align:center;">Browse {browse_label} →</a>
  </div>
</div>

<!-- ALERT - navy-deep -->
<div class="alert-wrap" id="alerts" data-nosnippet>
  <h2>Don't See The Right <span>Security Job</span> Yet?</h2>
  <p>New openings posted regularly across {alert_city}, {region}. Get notified the moment something matches.</p>
  <div class="alert-form" id="alertForm">
    <div class="alert-field"><span class="alert-field-icon">📍</span><input type="text" id="a-zip" placeholder="ZIP Code" inputmode="numeric" maxlength="5" pattern="[0-9]*"></div>
    <div class="alert-field"><span class="alert-field-icon">📱</span><input type="tel" id="a-ph" placeholder="Mobile Number" inputmode="tel"></div>
    <div class="alert-field"><span class="alert-field-icon">✉️</span><input type="email" id="a-em" placeholder="Email Address (optional)" inputmode="email"></div>
    <div id="alertError"></div>
    <a href="#" onclick="bbjAlertOpen();return false;" class="btn-primary" style="display:block;text-align:center;text-decoration:none;">Get Free Job Alerts →</a>
    <div class="alert-trust"><svg width="12" height="12" fill="none" viewBox="0 0 20 20"><path d="M10 2L3 6v5c0 4 3.1 7.7 7 8.9C13.9 18.7 17 15 17 11V6L10 2z" fill="rgba(255,195,0,0.6)"></path></svg> No spam. Unsubscribe anytime.</div>
    <p class="alert-note">By submitting I agree to receive SMS and email updates regarding jobs from BlackBarJobs. Msg &amp; data rates may apply. Reply STOP to unsubscribe.</p>
  </div>
  <div id="alertSuccess" style="display:none;text-align:center;padding:24px 0;">
    <div style="font-size:2.5rem;margin-bottom:10px;">✅</div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.6rem;font-weight:800;color:#fff;margin-bottom:5px;">You're On The List</div>
    <p style="color:rgba(255,255,255,0.55);font-size:0.88rem;">We'll notify you when {role} jobs open in {alert_city}.</p>
  </div>
</div>

<footer>
  <div class="footer-links">{ftlinks}</div>
  <div class="footer-logo">BlackBar<span>Jobs</span>.com</div>
  <p>Security job alerts for professionals across the US.</p>
  <p><a href="https://www.termsfeed.com/live/e651a49f-d387-4d53-baa2-d069b9f9677f" target="_blank">Privacy Policy</a></p>
</footer>

<script>
function toggleFaq(el){{el.parentElement.classList.toggle('open');}}
// Registration + attribution fire from the shared overlay (bbjAlertOpen /
// bbjAccOpen in /js/bbj-register-overlay.js) and its dataLayer events, caught
// by GTM. No inline conversion gtag, webhook fetch, or submitAlert() here.
(function(){{
  var b=document.getElementById('stickyBar'),h=document.querySelector('.hero');
  if(!b||!h)return;
  function chk(){{b.classList.toggle('show',h.getBoundingClientRect().bottom<=0);}}
  window.addEventListener('scroll',chk,{{passive:true}});chk();
}})();
</script>
<script>window.BBJ_FEED_KEY="{feed_key}";</script>
<script src="/js/bbj-feed.js" defer></script>
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<script src="/js/supabase-config.js"></script>
<script src="/js/bbj-auth-nav.js"></script>
<script src="/js/bbj-register-overlay.js"></script>
</body>
</html>"""

    assert_output_guardrails(html, slug)

    # ── Bake the job feed into the HTML on build (Lever 1, now at generation time) ──
    # Splice real job cards into the #indexJobFeed container between BBJ_BAKE markers,
    # reusing bbj_feed_bake.bake_page so the markup matches js/bbj-feed.js exactly.
    # Default on; set cfg["bake"]=False to emit the empty container (JS fills it live).
    baked_note = None
    if cfg.get("bake", True):
        try:
            html, _changed, baked_note = bake_page(html, feed_key, str(FEED_DIR), date.today())
        except BakeError as e:
            # Missing feed = a new page not yet snapshotted -> ship the empty container
            # (js/bbj-feed.js fills it live; re-run after the snapshot to bake). Any other
            # BakeError (mojibake, structural) is real corruption -> fail the build loudly.
            if "feed file missing" in str(e):
                baked_note = None
            else:
                raise SystemExit(f"BUILD BLOCKED — {slug}: feed bake failed: {e}")

    # Always surface the remaining manual steps so nothing is forgotten after a build.
    if cfg.get("print_next_steps", True):
        print(next_steps(cfg, feed_key, baked_note))

    return html

# ── Post-build reminder: the manual steps that remain after a page is generated ──
def next_steps(cfg, feed_key=None, baked_note=None):
    """Return the remaining-steps checklist for this page, with the real key, market,
    sitemap <loc>, and commands filled in. generate_page() prints this after every
    build (cfg["print_next_steps"]=False to silence) so nothing is left to guess.
    baked_note is bake_page()'s note ('5/5 jobs' / 'EMPTY') or None when no feed
    existed yet."""
    slug     = cfg["slug"]
    feed_key = feed_key or cfg.get("feed_key", slug.lstrip("/"))
    market   = cfg.get("market", "Houston")
    path     = cfg.get("path", slug.lstrip("/") + ".html")
    loc      = BASE_URL + slug
    if baked_note and baked_note != "EMPTY":
        status   = "cards baked into HTML (%s)" % baked_note
        snap_hint = "   (feed already exists; snapshot only needed to refresh)"
    else:
        status   = "NO cards baked yet -- empty container shipped, JS fills it live"
        snap_hint = "   (REQUIRED: creates feed/%s.json, then re-generate to bake)" % feed_key
    L = [
        "",
        "=" * 66,
        "NEXT STEPS  -  " + slug,
        "=" * 66,
        "  page file : " + path,
        "  feed key  : " + feed_key,
        "  status    : " + status,
        "",
        "  1. Register the target (key MUST byte-match the feed key above):",
        "       automation/bbj_page_targets.json  -- or call upsert_target_entry(cfg)",
        "  2. Snapshot the feed:",
        '       python automation/bbj_feed_snapshot.py --market "' + market + '" --out feed',
        snap_hint,
        "  3. Add this page to sitemap.xml (bake does NOT add new URLs):",
        "       <loc>" + loc + "</loc>",
        "  4. Audit before shipping:",
        "       python bbj_feed_target_check.py     (expect 0 missing)",
        "       python bbj_link_audit.py            (0 broken / 0 orphan)",
        "       python bbj_page_check.py",
        "  5. Commit on a branch, then push/merge (deploy gate).",
        "=" * 66,
        "",
    ]
    return "\n".join(L)

# ── New-page registration helpers (reduce manual bbj_page_targets.json errors) ──
def emit_target_entry(cfg):
    """Return the bbj_page_targets.json entry for this page, derived from cfg.

    'key' is derived from the same feed_key the page emits as BBJ_FEED_KEY, so the
    two can never drift (the mismatch that silently 404s a feed). The snapshot-only
    fields — feed_role / target_type / city_major / feed_city — drive job matching in
    bbj_feed_snapshot.py and are distinct from the human-facing cfg['role'] label, so
    set them in cfg for correct matching (feed_city should be a lowercase location
    token like 'dallas'; target_type is role | city | city-role | general)."""
    slug     = cfg["slug"]
    feed_key = cfg.get("feed_key", slug.lstrip("/"))
    city_tok = cfg.get("feed_city")
    if city_tok is None and not cfg.get("hub_mode"):
        city_tok = (cfg.get("city") or "").strip().lower() or None
    return {
        "key":            feed_key,
        "path":           cfg.get("path", slug.lstrip("/") + ".html"),
        "market":         cfg.get("market", "Houston"),
        "role":           cfg.get("feed_role"),
        "city":           city_tok,
        "city_major":     bool(cfg.get("city_major", False)),
        "target_type":    cfg.get("target_type", "general"),
        "container":      "indexJobFeed",
        "has_feed_block": True,
    }

def upsert_target_entry(cfg, targets_path="automation/bbj_page_targets.json"):
    """Opt-in: add/replace this page's entry in the manifest by key, keep 'pages' in
    sync, and write it back. Idempotent — re-running on an existing key replaces in
    place. Returns ('added'|'updated', total_pages). Call from the build driver; the
    generator never writes the manifest on its own."""
    entry = emit_target_entry(cfg)
    p = Path(targets_path)
    data = json.loads(p.read_text(encoding="utf-8"))
    targets = data.get("targets", [])
    for i, t in enumerate(targets):
        if t.get("key") == entry["key"]:
            targets[i] = entry
            action = "updated"
            break
    else:
        targets.append(entry)
        action = "added"
    data["targets"] = targets
    data["pages"] = len(targets)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return action, data["pages"]

print("BBJ Generator v5 loaded. Interlinking validation active. Feed baked on build.")
