BBJ PHASE 5  ·  Rewire pages from Google Sheet -> static JSON feed

WHAT THIS DOES
  Replaces the inline Google-Sheet CSV feed on each page with a 2-line hook that
  reads the page's static JSON snapshot via the shared /js/bbj-feed.js renderer.
  Visitor-facing markup and the click gate are unchanged. Covers 211 pages.
  Leaves 3 bespoke pages alone (handle separately): texas/security-guard-salary-texas,
  job-board.html, register-access.html.

FILES
  bbj-feed.js            -> goes in the repo at /js/bbj-feed.js
  bbj_page_targets.json  -> updated manifest (full subfolder paths). Replace your copy.
  bbj_feed_snapshot.py   -> unchanged; re-run it so feed files use the new full-path keys
  bbj_feed_patch.py      -> the page patcher (run from repo root)

DO THIS ON A GIT BRANCH WITH A VERCEL PREVIEW. Never straight to main.

STEP 0  new branch
  git checkout -b feed-migration

STEP 1  rebuild the snapshot with corrected keys
  (in your supabase-jobfeed folder, with SUPABASE_SERVICE_KEY set)
  replace bbj_page_targets.json with the one in this kit, then:
  python bbj_feed_snapshot.py
  -> writes the feed/ folder using full paths like feed/san-antonio/jobs/...

STEP 2  stage the new static assets into the repo
  copy  bbj-feed.js            -> <repo>/js/bbj-feed.js
  copy  the whole feed/ folder -> <repo>/feed/
  copy  bbj_feed_patch.py and bbj_page_targets.json -> <repo>/ (repo root)

STEP 3  patch ONE metro first
  cd <repo>
  python bbj_feed_patch.py --repo . --dry-run          (expect: would patch 211)
  python bbj_feed_patch.py --repo . --market "San Antonio" --no-backup
  git add -A && git commit -m "feed: SA pages -> static JSON" && git push -u origin feed-migration

STEP 4  verify on the Vercel preview
  open a San Antonio page on the preview URL. Confirm:
   - the job list renders (up to 5)
   - clicking a row still triggers the gate/apply
   - devtools Network shows /feed/san-antonio/....json returning 200

STEP 5  patch the rest, verify, merge
  python bbj_feed_patch.py --repo . --no-backup         (patches remaining metros)
  git add -A && git commit -m "feed: all pages -> static JSON" && git push
  verify a few DFW / Houston / Austin pages on the preview, then merge to main.

ROLLBACK
  You are on a branch, so git is your safety net (git checkout -- . or delete the branch).
  If you used backups instead of --no-backup:  python bbj_feed_patch.py --repo . --restore

NOTES
  - Do not commit .bak files. Using --no-backup avoids them (git is your rollback on a branch).
  - The feed/ folder and /js/bbj-feed.js are NEW files; make sure they get committed.
  - Re-running the patch is safe: already-patched pages are skipped.
