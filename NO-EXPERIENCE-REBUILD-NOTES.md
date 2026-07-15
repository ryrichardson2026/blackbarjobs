# Houston No-Experience Rebuild — Notes

Unzips at repo root; paths preserved.

## Files
- `houston/jobs/houston-no-experience-security.html` — rebuilt through the generator.
- `bbj_generator_v5.py` — updated: adds optional `h1_override` (default H1 format unchanged). **Review diff before overwriting root.**

## What changed on the page
- H1 → `Find the Latest Security Jobs in Houston, No Experience Required` (gold accent on the qualifier). Comma, not a dash (brand-safe).
- Hero feed brought up to the current golden hero-embedded model (`#indexJobFeed` in the form-card).
- Every em-dash in the ported copy converted to brand-safe punctuation.
- Placeholder feed baked in (data-baked + BBJ_BAKE markers, auto-replaced by bbj-feed.js live + the bake).

## Unchanged (SEO surface protected)
- Title tag, slug, canonical: identical.
- "No experience" stays the head term (title + slug + H1 qualifier + body).
- All 8 original interlinks preserved, including the training-schools link (satisfies licensing RULE 3) and the `/dallas` cross-market link.
- All ranking content ported verbatim (Twin City / Securitas / ACT / TriCorps, S.A.F.E. + NRG, Katy/Sugar Land/Woodlands HOA, $16.76 ZipRecruiter, Level 2 $47-100).

## Wording note
Confirmed a separate entry-level page exists (`/houston/jobs/houston-entry-level-security-jobs`), so keeping this page on "no experience" avoids cannibalizing it.

## Follow-up (standard)
Feed key `houston/jobs/houston-no-experience-security` already exists in your setup — re-run snapshot + bake to swap the placeholder for live cards. Then guardrail + page_check + link_audit before merge.

## Not included
The San Antonio no-experience, San Antonio warehouse, and Houston construction pages were NOT in the upload this round (only the Houston page was). Re-upload them and they'll get the identical treatment.
