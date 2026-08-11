#!/usr/bin/env python3
"""
bbj_indexing_test.py  ·  One-shot Indexing API verification

Submits a single URL_UPDATED notification to confirm the service account is
authenticated and recognized as an Owner in Search Console.

Submits ONE url. Does not touch the repo, Supabase, or the cron.

Setup:
    pip install google-auth requests

Usage (PowerShell):
    python bbj_indexing_test.py "C:\\path\\to\\key.json"
    python bbj_indexing_test.py "C:\\path\\to\\key.json" --url "https://www.blackbarjobs.com/houston/jobs/houston-airport-security"
    python bbj_indexing_test.py "C:\\path\\to\\key.json" --status   # read-only, no quota used
"""

import argparse, json, sys

try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
except ImportError:
    print("Missing dependency. Run:  pip install google-auth requests", file=sys.stderr)
    sys.exit(1)

SCOPE = "https://www.googleapis.com/auth/indexing"
# Google uses colon syntax for custom methods. A slash here returns an HTML 404.
PUBLISH = "https://indexing.googleapis.com/v3/urlNotifications:publish"
METADATA = "https://indexing.googleapis.com/v3/urlNotifications/metadata"
DEFAULT_URL = "https://www.blackbarjobs.com/houston/jobs/houston-airport-security"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keyfile", help="path to the service account JSON key")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--status", action="store_true",
                    help="read current indexing metadata instead of publishing (uses no publish quota)")
    args = ap.parse_args()

    try:
        with open(args.keyfile, encoding="utf-8") as f:
            key = json.load(f)
    except Exception as e:
        print(f"Could not read key file: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"service account : {key.get('client_email')}")
    print(f"project         : {key.get('project_id')}")
    print(f"target url      : {args.url}\n")

    creds = service_account.Credentials.from_service_account_info(key, scopes=[SCOPE])
    session = AuthorizedSession(creds)

    if args.status:
        r = session.get(METADATA, params={"url": args.url})
    else:
        r = session.post(PUBLISH, json={"url": args.url, "type": "URL_UPDATED"})

    print(f"HTTP {r.status_code}")
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text[:1000])

    print()
    if r.status_code == 200:
        print("SUCCESS. Auth and Search Console ownership are both working.")
        if not args.status:
            print("Google has queued this URL for recrawl. 1 of today's 200 publish requests used.")
    elif r.status_code == 403:
        body = r.text.lower()
        if "ownership" in body:
            print("FAIL: Search Console does not recognize this service account as an Owner.")
            print("  - Confirm the client_email above was added under Settings > Users and permissions")
            print("  - Permission must be Owner, not Full")
            print("  - If you have both a Domain and a URL-prefix property, add it to the one")
            print("    that covers the URL above (Domain property is safest)")
            print("  - Changes can take a few minutes to propagate")
        else:
            print("FAIL: 403. Most likely the Indexing API is not enabled on this project.")
            print("  https://console.cloud.google.com/apis/library/indexing.googleapis.com")
    elif r.status_code == 429:
        print("Rate limited. Daily quota is 200 publish requests, reset at midnight Pacific.")
    elif r.status_code == 404 and args.status:
        print("No metadata yet: this URL has never been submitted through the API. Expected on a first run.")
    else:
        print("Unexpected response. Full body above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
