# Holiday Cluster (complete) — Deploy Notes

Unzips at repo root; paths preserved. Review the generator diff, wire feeds, preview, merge.

## Files (6 pages + generator)

| Path | Notes |
|---|---|
| `holiday-security-jobs.html` | **National hub** (new). Hub-mode: "Seasonal Hiring" badge, 2-level breadcrumb, CollectionPage/ItemList schema, "Browse by City" directory linking all 5 metros. |
| `dallas/jobs/holiday-security-jobs-dfw.html` | DFW pilot (corrected). Hand-built vintage, same rendered look. |
| `houston/jobs/holiday-security-jobs-houston.html` | Generated. |
| `san-antonio/jobs/holiday-security-jobs-san-antonio.html` | Generated. |
| `austin/jobs/holiday-security-jobs-austin.html` | Generated. **Austin is IN** (full coverage). |
| `chicago/jobs/holiday-security-jobs-chicago.html` | Generated, IL (PERC/IDFPR, no TX leak). |
| `bbj_generator_v5.py` | **Updated — replaces root.** Adds hub-mode (badge/breadcrumb/schema/related-h2/browse-label overrides) + `h1_override`. Default metro behavior unchanged. Review diff. |

All pages use the clean generator model: hero-embedded feed (`#indexJobFeed` in the form-card), "Find the Latest …" H1, gold eyebrows, two-col splits, single Related Roles, FAQPage schema, "security officer" language, zero em-dashes. The hub is deliberately NOT built in the old blog/`#jobRows` layout.

## Placeholder feed
Every page ships a `data-baked="1"` + `BBJ_BAKE`-wrapped placeholder in `#indexJobFeed`. No page re-edit needed: `bbj-feed.js` refreshes it live once `feed/<key>.json` exists, and the build-time bake overwrites the marker region. `bbj-feed.js` is unchanged.

## Feed config (wire before merge)
Add each key to `automation/bbj_page_targets.json` + queries in `automation/bbj_feed_queries.json`, then snapshot + `bbj_feed_bake.py`:
- `holiday-security-jobs` (national — roll up all metros, deduped)
- `dallas/jobs/holiday-security-jobs-dfw` (exists; swap placeholder → real)
- `houston/jobs/holiday-security-jobs-houston`
- `san-antonio/jobs/holiday-security-jobs-san-antonio`
- `austin/jobs/holiday-security-jobs-austin`
- `chicago/jobs/holiday-security-jobs-chicago`

## Build steps
1. Drop in, branch. 2. Wire feed keys → snapshot → bake. 3. Feed guardrail + `bbj_page_check.py` + `bbj_link_audit.py`. 4. Add 6 URLs to `sitemap.xml`. 5. Vercel preview (confirm feed renders, overlay fires, Chicago reads IL, hub lists 5 metros). 6. Merge + resubmit sitemap.

## Flags
- **Interlink audit (your pass):** related_links / footer / resource slugs are best-guess canonicals; verify targets exist (esp. Chicago `/chicago/jobs/...` and `/illinois/...` guides).
- **Chicago firearm hours** left un-asserted (IDFPR vs FCC conflict).
- **DFW vintage:** hand-built; regenerate from the generator if you want uniform class names.

## Remaining cluster (not in this bundle)
Part-time cluster (5 metro pages + its own hub). The hub-mode you now have in the generator will build the part-time national hub the same way.
