This is a simple script to download App Store (iOS, MacOS) reviews for any given app.

To run it, you would need Python 3 and following incantantions (while in this repo folder):
```
source .venv/bin/activate
pip install -r requirements.txt
```

After that you can use the script as follows:
```
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
-s / --single_file  - saves every downloaded review to just ONE file,
                      named <app_id>-all.json (sorted newest to oldest).

Behavior
--------
• For every selected country the script calls Apple’s public RSS endpoint
  https://itunes.apple.com/{country}/rss/customerreviews/…
  paginates until no more reviews are returned, sleeps PAUSE_SECONDS
  between pages to stay polite, and saves the collected reviews to
  <output_folder>/<app_id>-<country>.json (newest → oldest).

• Passing the same country multiple times is allowed; duplicates are removed.

• An unknown country code aborts the run with an error message and exit status 1.
```

Since `outputs/` folder is in `.gitignore`, you can download reviews right there:
```
mkdir outputs/
python get_reviews.py <APP_ID> -c US --output_folder outputs/human_readable_name
```