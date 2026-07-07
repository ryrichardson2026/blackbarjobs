BBJ FEED KIT  ·  Phase 2 (fetch) + Phase 3 (snapshot)

FILES
  bbj_feed_fetch.py       Phase 2. Pulls searchapi Google Jobs -> Supabase jobs table.
  bbj_feed_snapshot.py    Phase 3. Reads Supabase -> writes per-page JSON into ./feed/
  bbj_feed_queries.json   164 queries (unarmed fix). Used by the fetch script.
  bbj_page_targets.json   209 page targets. Used by the snapshot script.

KEYS  (never go in the files or the repo; set them in PowerShell each session)
  $env:SEARCHAPI_KEY="..."            (fetch only)
  $env:SUPABASE_SERVICE_KEY="..."     (fetch + snapshot)

RUN
  # weekly fetch (fills the store)
  python bbj_feed_fetch.py --dry-run
  python bbj_feed_fetch.py

  # build page feeds (after a fetch)
  python bbj_feed_snapshot.py --market "San Antonio"
  python bbj_feed_snapshot.py

NOTES
  - Keep all 4 files in the same folder.
  - Two files changed since your first download: bbj_feed_queries.json (155 -> 164,
    added dedicated unarmed pulls) and bbj_feed_snapshot.py / bbj_page_targets.json are new.
    bbj_feed_fetch.py is unchanged from the version you already ran.
