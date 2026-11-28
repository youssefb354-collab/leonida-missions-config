#!/usr/bin/env python3
"""Checks an ads.json file before it goes live.

Exit code 0 = safe to publish. Errors stop the file from being used at all
(the app would fall back to its cached or bundled rules). Warnings point at
values the app will quietly clamp or ignore.

    python3 tools/validate_ads.py path/to/ads.json
"""
import json
import re
import sys

UNIT = re.compile(r"^ca-app-pub-\d{16}/\d{10}$")
FORMATS = ["banner", "interstitial", "rewarded", "appOpen"]
SCREENS = {"missionsList", "trackers", "search"}
RANGES = {
    ("interstitial", "everyNCompletions"): (2, 50),
    ("interstitial", "minSecondsBetween"): (60, 86400),
    ("interstitial", "minSecondsAfterLaunch"): (30, 3600),
    ("interstitial", "maxPerSession"): (0, 10),
    ("rewarded", "removeAdsHours"): (0, 72),
    ("rewarded", "themeHours"): (0, 72),
    ("appOpen", "minHoursInBackground"): (1, 168),
}
BOOLEANS = [("debugUseRemoteIds",), ("banner", "enabled"), ("interstitial", "enabled"),
            ("interstitial", "skipFirstSession"), ("rewarded", "enabled"), ("rewarded", "unlockMapLayers"), ("appOpen", "enabled")]
KNOWN = {"schemaVersion", "adsEnabled", "minAppVersion", "units", "banner", "interstitial", "rewarded", "appOpen", "debugUseRemoteIds"}


def validate(data):
    errors, warnings = [], []
    if not isinstance(data, dict):
        return ["the file must be a JSON object"], warnings
    if data.get("schemaVersion") != 1 or isinstance(data.get("schemaVersion"), bool):
        errors.append('"schemaVersion" must be 1 (the app ignores files with any other value)')
    if not isinstance(data.get("adsEnabled"), bool):
        errors.append('"adsEnabled" must be true or false')
    version = data.get("minAppVersion", "1.0.0")
    if not isinstance(version, str) or not re.match(r"^\d+(\.\d+){0,2}$", version):
        errors.append('"minAppVersion" must look like "1.0.0"')

    units = data.get("units", {})
    if not isinstance(units, dict):
        errors.append('"units" must be an object')
        units = {}
    for name in FORMATS:
        value = units.get(name)
        if value is None:
            warnings.append('no unit id for "%s": that format will be off' % name)
        elif not isinstance(value, str) or not UNIT.match(value):
            warnings.append('unit id for "%s" is not a valid AdMob ad unit id: that format will be off' % name)
        elif value.startswith("ca-app-pub-3940256099942544/"):
            warnings.append('unit id for "%s" is a Google TEST id: it earns nothing in production' % name)

    for path in BOOLEANS:
        node = data
        for key in path[:-1]:
            node = node.get(key, {}) if isinstance(node, dict) else {}
        if isinstance(node, dict) and path[-1] in node and not isinstance(node[path[-1]], bool):
            errors.append('"%s" must be true or false' % ".".join(path))

    for (section, key), (low, high) in RANGES.items():
        block = data.get(section, {})
        if not isinstance(block, dict):
            errors.append('"%s" must be an object' % section)
            continue
        if key not in block:
            continue
        value = block[key]
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append('"%s.%s" must be a whole number' % (section, key))
        elif not low <= value <= high:
            warnings.append('"%s.%s" is %d; the app will use %d (allowed: %d to %d)'
                            % (section, key, value, min(max(value, low), high), low, high))

    banner = data.get("banner", {})
    if isinstance(banner, dict) and "screens" in banner:
        screens = banner["screens"]
        if not isinstance(screens, list):
            errors.append('"banner.screens" must be a list')
        else:
            for screen in screens:
                if screen not in SCREENS:
                    warnings.append('unknown banner screen "%s" (known: %s)' % (screen, ", ".join(sorted(SCREENS))))
    for key in data:
        if key not in KNOWN:
            warnings.append('unknown key "%s" is ignored by the app' % key)
    return errors, warnings


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as error:
        print("ERROR: cannot read %s as JSON: %s" % (sys.argv[1], error))
        return 1
    errors, warnings = validate(data)
    for message in warnings:
        print("warning:", message)
    for message in errors:
        print("ERROR:", message)
    print("%s: %d error(s), %d warning(s)" % (sys.argv[1], len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
