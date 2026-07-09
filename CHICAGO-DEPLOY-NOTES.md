# BlackBarJobs - Chicago Market Deploy Notes

Complete Chicago property: **27 pages** (1 landing + 15 role/sector/industrial hubs + 6 content guides + 5 geo pages) and **21 seed feeds**. All internal links resolve; content accuracy-checked against IDFPR and current sources; FAQ CSS fix applied.

## File placement (drop into repo root, preserves structure)
- `chicago/index.html` -> serves at `/chicago`
- `chicago/chicago-security-jobs-guide.html` -> `/chicago/chicago-security-jobs-guide`
- `chicago/jobs/*.html` (20) -> `/chicago/jobs/<slug>`
- `illinois/*.html` (5) -> `/illinois/<slug>`
- `feed/chicago/index.json` + `feed/chicago/jobs/*.json` (20 seeds)
- `sitemap.xml` (updated, +27 URLs)

## Feed config (Claude Code - gitignored files)
For each of the 21 feed-backed pages below: add a `bbj_feed_queries.json` entry and a `bbj_page_targets.json` target, then run the snapshot to replace the seed with live jobs. Queries are security-anchored (taxonomy rule).

| Feed key `chicago/jobs/<slug>` (landing is `chicago/index`) | Query |
|---|---|
| `chicago/index` | security officer Chicago |
| `unarmed-security-chicago` | unarmed security officer Chicago |
| `armed-security-chicago` | armed security officer Chicago |
| `overnight-security-chicago` | overnight security officer Chicago |
| `event-security-chicago` | event security officer Chicago |
| `loss-prevention-chicago` | loss prevention officer Chicago |
| `airport-security-chicago` | airport security officer Chicago |
| `corporate-security-chicago` | corporate security officer Chicago |
| `hospital-security-chicago` | hospital security officer Chicago |
| `hotel-security-chicago` | hotel security officer Chicago |
| `campus-security-chicago` | campus security officer Chicago |
| `dispatch-security-chicago` | security dispatcher Chicago |
| `data-center-security-chicago` | data center security officer Chicago |
| `warehouse-security-chicago` | warehouse security officer Chicago |
| `manufacturing-security-chicago` | manufacturing security officer Chicago |
| `industrial-security-chicago` | industrial security officer Chicago |
| `security-officer-joliet` | security officer Joliet |
| `overnight-warehouse-security-joliet` | overnight warehouse security officer Joliet |
| `security-officer-naperville` | security officer Naperville |
| `security-officer-aurora` | security officer Aurora |
| `security-officer-schaumburg` | security officer Schaumburg |

The 6 content guides (`illinois/*` and the Chicago guide) have **no feed** - nothing to add for those.

## Before merge
1. Run guardrail + `bbj_page_check.py` + `bbj_link_audit.py` (expect 0 missing feeds, 0 broken links, 0 orphans).
2. **Geo gate:** the 5 geo pages ship only where the suburb feed returns ~15+ live security roles. Verify each before merging the thin ones (Naperville/Schaumburg most likely to be light).
3. Resubmit `sitemap.xml` in GSC after deploy.
4. Branch -> Vercel preview -> confirm a hub renders jobs and fires `alert_signup` -> merge.

## Out-of-state note
These pages were hand-built via clone-and-specialize (the generator is still dead code). If you wire the generator off these as the golden template, the city-aware `build()` and the added `:root` variable fix are the two changes to carry over.

## Sitewide changes in this pass (shared files - affect the whole site)
Two shared files changed and are included in this zip. They load on every page, so preview before merge.

1. **Nav (`js/bbj-auth-nav.js`)** - Chicago added to the Locations dropdown (DFW, Houston, San Antonio, Austin, **Chicago**). One edit, propagates to all 226+ pages via the shared nav injector.

2. **Job-board header (`job-board.html`)** - hardcoded "Texas" removed from the visible header (eyebrow + H1), now neutral by default. Added a dynamic-header script that reads `?city` / `?metro` / `?location` (or infers from UTM / `?role`) and sets the header to that metro, e.g. "Security Officer Jobs in Chicago" when arriving from a Chicago page. Also updates `document.title` in that case.

3. **Job-board filtering** - already works, no new code needed. The board reads `?role`/`?city`/`?metro`, matches role by prefix (so `armed-security-chicago` matches "armed"), and groups jobs by metro from live data. The Chicago pages' `bbjAccOpen` overlay already deep-links to `/job-board?role=<slug>&city=chicago`. Added `Chicago` to `METRO_FRIENDLY` for a clean label. **Requirement:** Chicago jobs must be in `feed/board.json`, which happens when the Chicago feed goes live and the snapshot runs (already in the feed-config step above).

## Follow-ups to consider (not done here)
- **Board body copy below the header is still Texas-authored** (the "Across Texas" H2, intro paragraph, FAQ, and "Texas License Guide" link). For a fully multi-metro board, neutralize or make those dynamic too. The default `<title>` also still says Texas (the dynamic script overrides it when a metro param is present).
- **Interlinking:** the Chicago pages are already densely interlinked (every hub's type grid links to all 15 hubs; related grid, area grid, guide grids; the pillar links to all 15 hubs + 5 suburbs). Optional quality refinement: make the per-page "related roles" contextual (e.g., hospital -> unarmed/overnight/campus/dispatch) instead of the shared generic five.
