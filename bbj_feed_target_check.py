#!/usr/bin/env python3
"""
bbj_feed_target_check.py  -  guardrail: every page that declares a BBJ_FEED_KEY
must have a matching feed/<KEY>.json committed in the repo.

WHY
  A landing/role page renders its job list by fetching /feed/<BBJ_FEED_KEY>.json
  (via js/bbj-feed.js). If that file was never generated, the fetch 404s and the
  page ships showing zero jobs -- silently. This catches that before it ships.

WHAT IT DOES
  Walks every .html page, reads its BBJ_FEED_KEY (if any), and checks that
  feed/<KEY>.json exists on disk. Prints any page pointing at a missing feed and
  exits non-zero so it can gate a push / CI.

RUN (from repo root)
  python bbj_feed_target_check.py
  python bbj_feed_target_check.py --path "C:\\Blacbar Jobs - SIte Folder\\blackbarjobs"

EXIT CODES
  0 = every BBJ_FEED_KEY resolves to a feed file
  1 = one or more pages point at a missing feed file
  2 = bad --path
"""

import os, re, argparse, sys

SKIP_DIRS = {".git", "node_modules", ".vercel", ".github", "_retired"}
KEY_RE = re.compile(r'BBJ_FEED_KEY\s*=\s*"([^"]+)"')


def feed_path_for(root, key):
    """Repo path that BBJ_FEED_KEY '<a>/<b>' must resolve to: <root>/feed/<a>/<b>.json"""
    return os.path.join(root, "feed", *key.split("/")) + ".json"


def main():
    ap = argparse.ArgumentParser(description="Verify every page's BBJ_FEED_KEY has a feed file.")
    ap.add_argument("--path", default=".", help="Repo root (default: current folder)")
    args = ap.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"Folder not found: {root}", file=sys.stderr)
        sys.exit(2)

    checked = 0
    missing = []   # (page_relpath, key, expected_feed_relpath)
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if not fn.lower().endswith(".html"):
                continue
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    html = fh.read()
            except Exception:
                continue
            m = KEY_RE.search(html)
            if not m:
                continue                      # page has no feed -> nothing to check
            key = m.group(1).strip()
            checked += 1
            if not os.path.isfile(feed_path_for(root, key)):
                feed_rel = ("feed/" + "/".join(key.split("/")) + ".json")
                missing.append((rel, key, feed_rel))

    print("=" * 64)
    print(f"BBJ FEED TARGET CHECK   ({checked} pages carry a BBJ_FEED_KEY)")
    print("=" * 64)

    if not missing:
        print("\n  OK - every BBJ_FEED_KEY resolves to a feed/<key>.json file.\n")
        sys.exit(0)

    print(f"\n  {len(missing)} page(s) point at a MISSING feed file:\n")
    for page, key, feed_rel in sorted(missing):
        print(f"  [MISSING] {page}")
        print(f"            BBJ_FEED_KEY = \"{key}\"")
        print(f"            expected     = {feed_rel}")
    print(f"\nFAIL - {len(missing)} missing feed target(s). Generate the snapshot "
          f"for these keys (or fix the key) before shipping.\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
