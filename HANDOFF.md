# BBJ Restructure — Handoff for Claude Code

**This restructure has NOT been applied to this repo yet. Perform it from scratch on a new branch.**
Earlier drafts of this file said the work was "already done" — ignore that. Nothing is done here.
This repo is in the pre-restructure state (full `jobs/` folder, no `dallas/` or `texas/` folder,
`employers-dfw.html` not yet renamed, old DFW homepage still at `/`). Your job is to do the whole move,
verify it, and push a branch for a Vercel preview. Work on a branch, never touch production directly,
and show a summary before pushing.

## Three finished pages are provided (place them as part of the move)
- national homepage — file titled "Security Officer Job Network" (may be named `national-index.html` to avoid clobbering the current homepage) -> becomes root `index.html`, canonical `/`
- `texas.html` -> `/texas/index.html` (TX hub, canonical `/texas`)
- the employers-tx page — file titled "Hire Security Officers in Texas" (may be named `employers-dfw (2).html`) -> `employers-tx.html` at root, canonical `/employers-tx`

Place these as the final step of the move. Until then, do not let the national page overwrite the current `index.html`.

## The restructure to perform
1. **Free `/`:** the current `index.html` is the old DFW homepage. Save it as `OLD-index-home.html.bak` (non-served), then put the national page at root as `index.html`.
2. **DFW cluster -> `/dallas/`:** move every `jobs/*.html` (and the whole `jobs/` subtree) to `dallas/*`. Move the root DFW pages (the `-dfw` / `dallas-` role, blog, and hub pages) into `dallas/` too. Build `/dallas` (the hub) from the ranking `security-jobs-dfw` page — that page becomes `dallas/index.html`, and `/security-jobs-dfw` 301s to `/dallas`. Result: `jobs/` empty.
3. **State resources -> `/texas/`:** move `texas-security-license-requirements`, `security-guard-salary-texas`, `how-to-become-a-security-guard-in-texas`, `security-jobs-for-veterans-texas` into `texas/`. Place the provided `texas.html` as `texas/index.html`.
4. **Employer rename:** `employers-dfw.html` -> `employers-tx.html` (serves `/employers-tx`). Repoint every internal `/employers-dfw` link to `/employers-tx`. Add a permanent 301 `/employers-dfw` -> `/employers-tx`.
5. **Dedup:** collapse pages that exist at BOTH root and `/jobs` to one canonical each — the canonical tag already in each page declares the winner (6 role hubs + `full-time-security-jobs-dfw` -> the `/jobs` copy wins; `security-jobs-dfw` + `texas-security-license-requirements` -> the root copy wins). Collapse 3 near-dups: `irving-overnight-security` -> `irving-overnight-security-jobs`; `mobile-patrol-security-jobs-dfw` -> `mobile-patrol-dfw`; `dallas-hospital-security` -> `dallas-hospital-healthcare-security`. Loser 301s to winner.
6. **Rewrite internal links** across all HTML to the new paths (root-relative). Also update generator inputs `pages.json`, `inject-footer-links.js`, `fix-related-links.js`.
7. **Sitemap:** regenerate `sitemap.xml` from live 200 pages only (new paths), excluding auth/util pages (login, dashboard, register, register-access, job-board).
8. **Redirects:** in `vercel.json`, add permanent 301s old->new for every moved/collapsed/renamed URL. No chains (no source that is also a destination). No source that is also a live file. Preserve existing Houston redirects.
9. **Leave other markets alone:** do NOT move Houston/SA/Austin pages. Only collapse their stray root duplicate landers if present (`security-jobs-austin`, `security-jobs-san-antonio`, `how-to-hire-security-houston` already exist inside their folders — 301 the root copies to the folder copies).

## Verify before pushing (fix anything that fails)
1. Dead internal links: every `href` resolves to a real file (respect `cleanUrls`). Expect 0.
2. No residual old paths in HTML: zero `href="/jobs/`, zero `href="/security-jobs-dfw"`, zero `href="/employers-dfw"`.
3. No double-prefix paths: nothing like `/dallas/dallas/...`, `/texas/texas/...`, `/houston/houston/...`.
4. Canonicals + `og:url` match each page's real served URL.
5. Sitemap lists only live 200 URLs, no redirected/removed ones.
6. `vercel.json` redirects: no chains, no source that is also a live file.
7. Houston/SA/Austin paths (`/houston/jobs/*`, `/san-antonio/jobs/*`, `/austin/jobs/*`) unchanged.
8. Run `bbj_link_graph.py` — report orphans/dead links. Acceptable orphans: auth/util pages, deep job-description pages, pre-existing Houston/SA mesh-gap pages. New orphans on `/`, `/texas`, `/dallas`, or `/employers-tx` are NOT acceptable — wire them into nav/footer.
9. Run `bbj_tracking_audit.py` — report tracking-fire drift; single firing point should remain `js/bbj-register-overlay.js` + GTM dataLayer.
10. Confirm `bbj_generator_v5.py` output paths emit `/dallas` and `/texas` (not `/jobs/` and root) so a future regen won't undo this. If it still emits old paths, patch it.

## Then
- Show a summary of counts and every fix made.
- Push the branch so Vercel builds a preview. Do NOT merge to main.
- After preview, owner spot-checks `/`, `/texas`, `/dallas`, `/dallas/dallas-overnight-security`, `/employers-tx` and an old URL like `/security-jobs-dfw` (should 301 to `/dallas`). Owner merges.

## Off-repo (owner does these; not your job)
- Google Ads final URLs on active campaigns -> new paths (ads to `/` are being turned off, skip those).
- GTM triggers keyed on `/jobs/` -> `/dallas/`.
- Outreach email body + MailerLite: `/employers-dfw` -> `/employers-tx`.
- Submit new `sitemap.xml` in GSC; keep old URLs crawlable so 301s pass.

## Guardrails
- This moves live, ranking pages — highest-risk operation on the site. Branch-first, verify before push, never touch production directly.
- Surgical edits: read before writing, change only what's needed, verify.
- When rewriting paths, match full quoted tokens — never a bare `/jobs/` substring (it lives inside `/houston/jobs/`, and a naive replace corrupts Houston/SA/Austin paths).
