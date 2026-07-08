# BlackBarJobs: Project Standards (CLAUDE.md)

Read this fully at the start of every session and follow it on every change.
BlackBarJobs (BBJ) is a static HTML/JS security officer candidate network and
publisher property targeting Texas markets, hosted on Vercel via GitHub, with
static per-page JSON job feeds (searchapi.io ingest + Supabase, snapshotted to
/feed/*.json), Supabase auth, and Make.com/MailerLite for leads.
Candidate traffic is the product; employer demand develops as rankings grow.

---

## 1. Copy and language (non-negotiable)
- Always write "security officer", never "security guard", in all copy, meta, schema, UI, and outreach.
- No em-dashes in any marketing copy, page copy, or outreach. Use commas, periods, or restructure.
- No AI-sounding phrasing. Write plainly, like an operator.
- Meta descriptions are action-forward and under ~155 characters.

## 2. Edit discipline (critical, these pages rank)
- Surgical edits only: read the file first, confirm the exact lines, change only those, verify, then commit. Never rewrite a file wholesale.
- Never run a blind full-strip regex across pages. Data-loss risk. Use targeted, per-variant replacements and verify each.
- DFW pages are ranking and climbing toward page one. Edits to live ranking pages must be conservative and surgical.
- Bulk HTML patching walks the tree with os.walk and excludes .git, node_modules, .vercel.
- After any bulk or multi-page change, re-run the audits (Section 8) and report results before committing.

## 3. Brand
- Colors: navy #000814 and #001D3D, gold #FFC300.
- Type: headings Barlow Condensed (600/700/800), body Barlow (400/500/600).
- Fonts loaded from Google Fonts as in the generator head.

## 4. Page structure and style routing
Two distinct concepts. Do not conflate them.

Pillar vs hub:
- Pillar pages (for example /dallas/dallas-security-jobs-guide) are 3,000 to 5,000 word guides, NOT hub directories.
- Hub, geo, topic, and role pages are directory/landing pages.

Visual template routing (which page to copy structure from):
- index.html: the homepage, employer pages, and any lead-magnet / index page.
- unarmed-security-dfw.html: every hub, geo, topic, neighborhood, licensing, training, role, and content page.

Mandatory DFW hub batch: any change to a DFW role hub touches ALL SIX together, in /jobs/:
unarmed-security-dfw.html, armed-security-dfw.html, overnight-security-dfw.html,
event-security-dfw.html, loss-prevention-dfw.html, tsa-airport-security-dfw.html.
Never skip one or treat them separately.

## 5. SEO and meta (source of truth = bbj_generator_v5.py)
Do not reinvent SEO per page. The generator head is the contract. Every page carries:
- title, reused as og:title.
- meta description, reused as og:description and twitter:description.
- canonical = BASE_URL + slug (auto-derived).
- robots: index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1.
- favicon set (ico, 32, 64, apple-touch).
- Open Graph: title, description, url, type=website. Twitter: summary_large_image + description.
- Three JSON-LD blocks on every page: FAQPage, JobPosting, BreadcrumbList (BlackBarJobs → market hub → role).
- Analytics: GTM-TP9JXK39, Clarity wvxhs1xht1, Google Ads AW-17039190320. GA4 property G-2H5B3H6NMT.
Known gaps to fix deliberately, not silently:
- JobPosting addressRegion is hardcoded "TX". Tokenize before any out-of-state market.
- twitter:card is summary_large_image but no og:image / twitter:image is emitted. Add an image tag if using image cards.

## 6. Interlinking (hard requirement, every page, enforced)
The mesh must be uniform so Search Console can crawl and discover every page. Rules by page
type (see detect_page_type in bbj_generator_v5.py):
- ALL pages link to their market hub: DFW=/dallas, Houston=/houston, San Antonio=/san-antonio, Austin=/austin.
- topic and role_hub pages include a cross-market link to the equivalent page in another market.
- licensing pages link to the market's training-schools page (or the Texas-wide license page).
- topic pages link to at least one suburb hub. suburb_hub pages link to at least two sibling suburb hubs.
- neighborhood pages link up to a primary topic page.
- No orphans: every new page must be linked FROM at least one existing hub or topic in the same change. A page with zero inbound links does not ship.
- No dead links: never link to a page that does not exist.
Enforcement:
- bbj_generator_v5.py hard-gates the outbound rules per page. A violation raises BUILD BLOCKED. Override only with a conscious skip_interlink_gate=True in that page's cfg.
- bbj_link_audit.py checks inbound links and reachability across the whole repo. Run it before every push; orphans, unreachable pages, and dead links block the push.

## 7. Tracking and overlays (one source of truth)
- The signup webhook and attribution fire from ONE place: js/bbj-register-overlay.js (bbjAlertOpen, bbjAccOpen), which every page loads.
- The bbjAttr helper captures attribution once at landing (gclid/gbraid/wbraid, utm_*, referrer, derived channel) and persists it for the session. Every payload includes page_url, landing_url, channel, and cta.
- Do NOT add new inline webhook fetches or inline Ads-conversion gtag calls to pages.
- Conversions belong in GTM, fired off the dataLayer events the shared script pushes (alert_signup, account_created, bbj_access_signup), not inline per page.
- RESOLVED (2026-07-08): bbj_generator_v5.py no longer emits an inline fetch(WEBHOOK), an inline gtag conversion, or a submitAlert() block. Generated pages now load js/bbj-register-overlay.js and fire registration only via bbjAlertOpen()/bbjAccOpen() and the shared dataLayer events, caught by GTM. Regenerating pages is safe on the tracking front. Do NOT reintroduce inline webhook/conversion fires into the template.

## 8. Tooling and audits
- bbj_generator_v5.py: page generator. SEO/meta/schema contract, page-type detection, interlinking gate. Each page emits BBJ_FEED_KEY (= slug without leading slash) and loads js/bbj-feed.js; the visible-job cap and apply gating live in that shared script. Also bakes in two output guardrails: no internal <a href> may carry a utm_ param, and the favicon set must be present, or the build blocks.
- bbj_page_check.py: audits every page for correct wiring (GTM, shared overlay, BBJ_FEED_KEY + bbj-feed.js, auth scripts) and flags leftover old systems (submitAlert, inline conversion/webhook, CSV feeds), wrong-metro copy, and em-dashes. Run after tracking/overlay/feed changes.
- bbj_link_audit.py: cross-checks pages, internal links, and sitemaps; reports broken links, dead sitemap URLs, pages missing from the map, orphans, and dead links. Run before every push.
- Feeds: static per-page JSON snapshots at /feed/<BBJ_FEED_KEY>.json (searchapi.io ingest + Supabase), rendered by js/bbj-feed.js. The old Google Sheets CSV feed (PUB_BASE + MASTER_* GIDs) is retired.

## 9. Markets
- Live: DFW, Houston.
- In progress / queued: San Antonio, Austin (need feeds wired to /feed/*.json, full mesh, and parity buildout).
- New-market and role pages are structural clones per Section 4, with city-specific content swapped and all source-market references scrubbed.

## 10. Workflow
- Work on a branch, never directly on main, so Vercel builds a preview instead of shipping to production.
- Show the diff for review before merge. Ranking pages get extra scrutiny.
- After multi-page changes: run bbj_link_audit.py and bbj_page_check.py, report results, then commit.
- Keep commits deliberate. Do not auto-push every edit.

## 11. Outreach
- Employer page https://www.blackbarjobs.com/employers-dfw must appear in every outreach email body.
- Signature: Thanks, Ryaire Richardson | BlackBarJobs.com | Founder | 206.883.8017
- "security officer" throughout, no em-dashes, no AI-sounding phrasing.

## 12. Working autonomously
- Run the full loop end to end without pausing between steps: branch -> make the surgical edits ->
  run the relevant audit (bbj_page_check.py / bbj_link_audit.py) -> commit.
- Only stop to ask when: (1) about to git push or merge, (2) a fix is genuinely ambiguous, or
  (3) a change would touch working functionality.
- After any page or link change, re-run the audits and report the before/after counts.
- Surgical edits only. Branch first. Never edit on main.
