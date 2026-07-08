BBJ deploy bundle — paths mirror the repo, drop straight in.

FILES & DESTINATIONS
  index.html            -> /index.html            (root homepage)
  dallas/index.html     -> /dallas/index.html      (DFW landing page)
  js/bbj-auth-nav.js    -> /js/bbj-auth-nav.js      (standardized nav, sitewide)

WHAT CHANGED
  index.html
    - Stripped UTM params off the two internal /job-board links (nav + hero).
      Favicon already present; no other change.

  dallas/index.html  (the real DFW landing page, brought to current standard)
    - Replaced old inline registration modal system with the shared overlay
      (bbj-register-overlay.js); CTAs now call bbjAlertOpen()/bbjAccOpen().
    - Removed old Make.com webhook + inline gtag conversion fires + stale
      alert_form_submit event.
    - Swapped retired Google Sheets CSV feed for the static-JSON system
      (window.BBJ_FEED_KEY="dallas/index" + bbj-feed.js).
    - Preserved working toggleFaq + sticky-bar helpers.
    - Added canonical (/dallas) and fixed og:url to /dallas.
    NOTE: feed/dallas/index.json does not exist yet (404). Run the snapshot
    pipeline (bbj_feed_snapshot.py) to generate it, or it lands on the next
    Tuesday automation run. Until then the page shows skeleton rows.

  js/bbj-auth-nav.js  (drop-in replacement — already loads on every page)
    - Injects the standardized menu sitewide, no per-page edits:
        Logo -> /
        Locations v : Dallas-Fort Worth /dallas, Houston /houston,
                      San Antonio /san-antonio, Austin /austin
        Find Jobs   -> /job-board
        Employers v : Hire Officers /employers-tx, Hiring Guides /#employers
        Resources   -> /#resources
        About Us    -> /about
        + Sign In (/login.html) / Sign Out (-> /job-board), state-based
    - Strips legacy nav content first (homepage inline menu, about.html
      "Back to Jobs", old Get Alerts CTA); keeps the logo.
    - Hamburger menu under 860px; dropdowns tap open/closed.
    - To add a market later, edit MENU_HTML in this one file.

DEPLOY
  Branch -> Vercel preview -> review -> merge. Hard-refresh when testing the
  nav so you are not served the cached bbj-auth-nav.js.

STILL OPEN (not in this bundle)
  - The guide currently at /dallas needs a new home before dallas/index.html
    is overwritten (decide: retire vs move to its own slug).
  - Interlinks on the DFW landing were left as-is (not ported).
