# BlackBarJobs: Project Standards (CLAUDE.md)

Read this fully at the start of every session and follow it on every change.
BlackBarJobs (BBJ) is a static HTML/JS security officer candidate network and
publisher property targeting Texas markets, hosted on Vercel via GitHub, with
Google Sheets CSV job feeds, Supabase auth, and Make.com/MailerLite for leads.
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
- Pillar pages (for example /security-jobs-dfw) are 3,000 to 5,000 word guides, NOT hub directories.
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
- ALL pages link to their market hub: DFW=/security-jobs-dfw, Houston=/houston, San Antonio=/san-antonio, Austin=/austin.
- topic and role_hub pages include a cross-market link to the equivalent page in another market.
- licensing pages link to the market's training-schools page (or the Texas-wide license page).
- topic pages link to at least one suburb hub. suburb_hub pages link to at least two sibling suburb hubs.
- neighborhood pages link up to a primary topic page.
- No orphans: every new page must be linked FROM at least one existing hub or topic in the same change. A page with zero inbound links does not ship.
- No dead links: never link to a page that does not exist.
Enforcement:
- bbj_generator_v5.py hard-gates the outbound rules per page. A violation raises BUILD BLOCKED. Override only with a conscious skip_interlink_gate=True in that page's cfg.
- bbj_link_graph.py checks inbound links and reachability across the whole repo. Run it before every push; orphans, unreachable pages, and dead links block the push.

## 7. Tracking and overlays (one source of truth)
- The signup webhook and attribution fire from ONE place: js/bbj-register-overlay.js (bbjAlertOpen, bbjAccOpen), which every page loads.
- The bbjAttr helper captures attribution once at landing (gclid/gbraid/wbraid, utm_*, referrer, derived channel) and persists it for the session. Every payload includes page_url, landing_url, channel, and cta.
- Do NOT add new inline webhook fetches or inline Ads-conversion gtag calls to pages.
- Conversions belong in GTM, fired off the dataLayer events the shared script pushes (alert_signup, account_created, bbj_access_signup), not inline per page.
- CAVEAT: bbj_generator_v5.py currently bakes an inline fetch(WEBHOOK) and inline gtag conversion into each page's submitAlert(). This is the source of historical drift. Regenerating pages re-introduces inline fires. Refactor the generator template to rely on the shared script + GTM before any mass regeneration.

## 8. Tooling and audits
- bbj_generator_v5.py: page generator. SEO/meta/schema contract, page-type detection, interlinking gate. PUB_BASE + MASTER_* constants are the feed source of truth. San Antonio and Austin master GIDs are still TODO placeholders pointing at the DFW GID. Replace before those feeds go live.
- bbj_tracking_audit.py: inventories inline webhook/conversion drift across all pages. Run after tracking changes.
- bbj_link_graph.py: builds the internal link graph; reports orphans, unreachable pages, dead links. Run before every push.
- Feeds: Google Sheets published CSV per tab (PUB_BASE in the generator). DFW master gid 885752320, Houston master gid 1720400336.

## 9. Markets
- Live: DFW, Houston.
- In progress / queued: San Antonio, Austin (need feed GIDs, full mesh, and parity buildout).
- New-market and role pages are structural clones per Section 4, with city-specific content swapped and all source-market references scrubbed.

## 10. Workflow
- Work on a branch, never directly on main, so Vercel builds a preview instead of shipping to production.
- Show the diff for review before merge. Ranking pages get extra scrutiny.
- After multi-page changes: run bbj_link_graph.py and bbj_tracking_audit.py, report results, then commit.
- Keep commits deliberate. Do not auto-push every edit.

## 11. Outreach
- Employer page https://www.blackbarjobs.com/employers-dfw must appear in every outreach email body.
- Signature: Thanks, Ryaire Richardson | BlackBarJobs.com | Founder | 206.883.8017
- "security officer" throughout, no em-dashes, no AI-sounding phrasing.
