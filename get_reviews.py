#!/usr/bin/env python3
"""
Download public App Store customer-reviews for any app.

USAGE
-----
Minimal:                  python get_reviews.py <APP_ID>
Pick specific countries:  python get_reviews.py <APP_ID> -c US -c FR -c DE
Custom output folder:     python get_reviews.py <APP_ID> -c US --output_folder /tmp

Arguments
---------
positional APP_ID   – the numeric Apple “trackId”, as seen in the App Store URL
-c / --country      – 2-letter App Store country code (ISO-3166-1).
                      May be given several times.  If omitted, all countries are used.
--output_folder     – destination directory for the JSON files (defaults to cwd)

Behavior
--------
• For every selected country the script calls Apple’s public RSS endpoint
  https://itunes.apple.com/{country}/rss/customerreviews/…
  paginates until no more reviews are returned, sleeps PAUSE_SECONDS
  between pages to stay polite, and saves the collected reviews to
  <output_folder>/<app_id>-<country>.json (newest → oldest).

• Passing the same country multiple times is allowed; duplicates are removed.

• An unknown country code aborts the run with an error message and exit status 1.
"""
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

import requests

########################################################################
# You may tweak this – increase if you ever get HTTP 403s or timeouts. #
PAUSE_SECONDS = 1.0
########################################################################

# ---------------------------------------------------------------------
# Hard-wire the 116 official App Store storefronts (taken from the CSV
# you provided so that the script is self-contained).
# ---------------------------------------------------------------------
_COUNTRY_MAP = {
    'DZ': 'Algeria', 'AO': 'Angola', 'AI': 'Anguilla', 'AR': 'Argentina',
    'AM': 'Armenia', 'AU': 'Australia', 'AT': 'Austria', 'AZ': 'Azerbaijan',
    'BH': 'Bahrain', 'BB': 'Barbados', 'BY': 'Belarus', 'BE': 'Belgium',
    'BZ': 'Belize', 'BM': 'Bermuda', 'BO': 'Bolivia', 'BW': 'Botswana',
    'BR': 'Brazil', 'VG': 'British Virgin Islands', 'BN': 'Brunei Darussalam',
    'BG': 'Bulgaria', 'CA': 'Canada', 'KY': 'Cayman Islands', 'CL': 'Chile',
    'CN': 'China', 'CO': 'Colombia', 'CR': 'Costa Rica', 'HR': 'Croatia',
    'CY': 'Cyprus', 'CZ': 'Czech Republic', 'DK': 'Denmark', 'DM': 'Dominica',
    'EC': 'Ecuador', 'EG': 'Egypt', 'SV': 'El Salvador', 'EE': 'Estonia',
    'FI': 'Finland', 'FR': 'France', 'DE': 'Germany', 'GH': 'Ghana',
    'GB': 'Great Britain', 'GR': 'Greece', 'GD': 'Grenada', 'GT': 'Guatemala',
    'GY': 'Guyana', 'HN': 'Honduras', 'HK': 'Hong Kong', 'HU': 'Hungary',
    'IS': 'Iceland', 'IN': 'India', 'ID': 'Indonesia', 'IE': 'Ireland',
    'IL': 'Israel', 'IT': 'Italy', 'JM': 'Jamaica', 'JP': 'Japan',
    'JO': 'Jordan', 'KE': 'Kenya', 'KW': 'Kuwait', 'LV': 'Latvia',
    'LB': 'Lebanon', 'LT': 'Lithuania', 'LU': 'Luxembourg', 'MO': 'Macau',
    'MG': 'Madagascar', 'MY': 'Malaysia', 'ML': 'Mali', 'MT': 'Malta',
    'MU': 'Mauritius', 'MX': 'Mexico', 'MS': 'Montserrat', 'NP': 'Nepal',
    'NL': 'Netherlands', 'NZ': 'New Zealand', 'NI': 'Nicaragua', 'NE': 'Niger',
    'NG': 'Nigeria', 'NO': 'Norway', 'OM': 'Oman', 'PK': 'Pakistan',
    'PA': 'Panama', 'PY': 'Paraguay', 'PE': 'Peru', 'PH': 'Philippines',
    'PL': 'Poland', 'PT': 'Portugal', 'QA': 'Qatar',
    'MK': 'Republic of North Macedonia', 'RO': 'Romania', 'RU': 'Russia',
    'SA': 'Saudi Arabia', 'SN': 'Senegal', 'SG': 'Singapore', 'SK': 'Slovakia',
    'SI': 'Slovenia', 'ZA': 'South Africa', 'KR': 'South Korea', 'ES': 'Spain',
    'LK': 'Sri Lanka', 'SR': 'Suriname', 'SE': 'Sweden', 'CH': 'Switzerland',
    'TW': 'Taiwan', 'TZ': 'Tanzania', 'TH': 'Thailand', 'TN': 'Tunisia',
    'TR': 'Turkey', 'UG': 'Uganda', 'UA': 'Ukraine',
    'AE': 'United Arab Emirates', 'US': 'United States', 'UY': 'Uruguay',
    'UZ': 'Uzbekistan', 'VE': 'Venezuela', 'VN': 'Vietnam', 'YE': 'Yemen'
}
_ALL_CODES = set(_COUNTRY_MAP.keys())


# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------
def fetch_country_reviews(app_id: str, country: str) -> List[Dict]:
    """
    Download *all* reviews for a single <app_id, country> combination
    using Apple's public RSS endpoint. Returns a list of dicts.
    """
    reviews: List[Dict] = []
    page = 1
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0 (compatible; app-review-scraper)"}

    while True:
        url = (
            f"https://itunes.apple.com/{country.lower()}/rss/customerreviews/"
            f"page={page}/sortby=mostrecent/id={app_id}/json"
        )

        resp = session.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            # 404 means the app is not available in this storefront
            break

        data = resp.json()
        feed = data.get("feed", {})
        entries = feed.get("entry", [])
        if not entries:
            break

        # Normalize: make sure we always have a list
        # because if our API call returned just one review, `entries` will
        # be a dict, not [dict]
        if isinstance(entries, dict):
            entries = [entries]

        for e in entries:
            if not isinstance(e, dict):
                print(f" BROKEN FEED: {data}", file=sys.stderr)
                continue

            review = {
                "id": e["id"]["label"],
                "author": e["author"]["name"]["label"],
                "version": e["im:version"]["label"],
                "rating": int(e["im:rating"]["label"]),
                "title": e["title"]["label"],
                "content": e["content"]["label"],
                "voteCount": int(e["im:voteCount"]["label"]),
                "voteSum": int(e["im:voteSum"]["label"]),
                "date": e["updated"]["label"],
                "country": country.upper(),
            }
            reviews.append(review)

        # pagination: if there is no rel="next" link, stop
        links = feed.get("link", [])
        has_next = any(
            (link.get("attributes", {}).get("rel") == "next") for link in links
        )
        if not has_next:
            break

        page += 1
        time.sleep(PAUSE_SECONDS)

    # newest -> oldest
    reviews.sort(
        key=lambda r: dt.datetime.strptime(r["date"], "%Y-%m-%dT%H:%M:%S%z"),
        reverse=True,
    )
    return reviews


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
class _ArgumentParser(argparse.ArgumentParser):
    """Print full help on any argument-error, then exit."""
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"\nError: {message}\n\n")
        self.print_help(sys.stderr)
        sys.exit(2)

def parse_args() -> argparse.Namespace:
    parser = _ArgumentParser(
        description="Download public App Store customer-reviews for any app, one file per country, each sorted newest to oldest",
        allow_abbrev=False,
    )
    parser.add_argument(
        "app_id",
        nargs="?",
        help="Numeric Apple app id (trackId). Required.",
    )
    parser.add_argument(
        "-c",
        "--country",
        action="append",
        help="2-letter country code. Can be used multiple times. "
             "If omitted, all countries are used.",
    )
    parser.add_argument(
        "--output_folder",
        default=".",
        help="Destination directory. Defaults to current working directory.",
    )
    parser.add_argument(
        "--single_file", "-s",
        action="store_true",
        help=("Save every downloaded review to just ONE file "
              "named <app_id>-all.json (sorted newest to oldest).")
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    combined: list[dict] = []
    seen_ids: set[str] = set()

    # If no app id was given: print help/description and exit.
    if not args.app_id:
        print(__doc__)
        sys.exit(0)

    app_id = args.app_id.strip()

    # Countries
    if args.country:
        requested = {c.upper() for c in args.country}
        unknown = requested - _ALL_CODES
        if unknown:
            print(
                f"Fatal: unknown App Store country code(s): {', '.join(sorted(unknown))}",
                file=sys.stderr,
            )
            sys.exit(1)
        countries = sorted(requested)
    else:
        countries = sorted(_ALL_CODES)

    out_dir = Path(args.output_folder).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"Fetching reviews for app {app_id} "
        f"({len(countries)} country{'s' if len(countries)!=1 else ''})."
    )

    for c in countries:
        print(f"  • {c} – downloading …", end="", flush=True)
        try:
            reviews = fetch_country_reviews(app_id, c)
        except Exception as exc:
            print(f" ERROR ({exc})")
            continue

        # add to a merged list (dedup by review id)
        for r in reviews:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                combined.append(r)
            else:
                print(f" duplicated review")

        # per-country file only if single_file not requested
        if not args.single_file:
            outfile = out_dir / f"{app_id}-{c.lower()}.json"
            with outfile.open("w", encoding="utf-8") as f:
                json.dump(reviews, f, ensure_ascii=False, indent=2)
            print(f" saved {len(reviews):>6} reviews → {outfile}")
        else:
            print(f" collected {len(reviews):>6} reviews")

    if args.single_file:
        # newest → oldest
        combined.sort(
            key=lambda r: dt.datetime.strptime(r["date"], "%Y-%m-%dT%H:%M:%S%z"),
            reverse=True,
        )
        outfile = out_dir / f"{app_id}-all.json"
        with outfile.open("w", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)
        print(f"\nMerged {len(combined)} unique reviews → {outfile}")

    print("Done.")


if __name__ == "__main__":
    main()
