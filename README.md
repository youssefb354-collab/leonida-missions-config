# Leonida Missions – remote files

Public files the Leonida Missions app downloads, plus its privacy policy page.

| File | Purpose |
|---|---|
| `manifest.json` | Which content version is current |
| `content.json` | Missions, trackers, regions, news |
| `ads.json` | Ad rules (kill switch, unit ids, frequency) |
| `privacy.html`, `index.html` | Website served by GitHub Pages |
| `app-ads.txt` | Authorised ad sellers, for AdMob verification |

Every push is checked by `.github/workflows/validate.yml`. Before committing, run:

    python3 tools/validate_ads.py ads.json
    python3 tools/validate_content.py content.json --manifest manifest.json

To publish new content: edit `content.json`, raise its `contentVersion`, set the same number in `manifest.json`, commit both.

To turn all ads off at once: set `"adsEnabled": false` in `ads.json`.

Leonida Missions is an unofficial fan-made guide. It is not affiliated with, endorsed, sponsored, or approved by Rockstar Games or Take-Two Interactive.
