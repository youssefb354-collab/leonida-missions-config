#!/usr/bin/env python3
"""Checks content.json before it is bundled or published.

Applies the same rules as the app (`ContentValidator.swift`): the schema,
duplicate ids, broken references, coordinates outside 0 to 1, plus checks
that only matter when publishing: missing translations, pins in the sea,
and source-site names leaking into text players can read.

    python3 tools/validate_content.py LeonidaMissions/Resources/content.json
    python3 tools/validate_content.py content.json --manifest manifest.json --languages en,fr,es

Exit code 0 = no errors (warnings are printed but do not fail).
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MISSION_TYPES = {"story", "side", "stranger", "heist", "heist-setup", "random-event", "other"}
TRACKER_KINDS = {"collectible", "activity", "vehicle", "weapon", "property", "trophy", "shop", "other"}
CHARACTERS = {"jason", "lucia", "both"}
COLOURS = {"night", "dusk", "sunsetPink", "sunsetOrange", "gold", "aqua", "text", "textDim", "pink", "orange"}
MARKUP = re.compile(r"\{([a-zA-Z]+):([^{}]*)\}")
# Names of sites used for research must never show up in player-facing text.
SOURCE_NAMES = re.compile(
    r"powerpyx|gtabase|gta6wiki|gamerant|game rant|pushsquare|push square|fextralife|\bign\b|thegamer|gamingpromax|"
    r"beebom|dexerto|gtaside|gfinity|egamers|mobalytics|according to|sources? (say|disagree|differ)|https?://",
    re.IGNORECASE)


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, message):
        self.errors.append(message)

    def warning(self, message):
        self.warnings.append(message)


def texts(value):
    """Every language string of a localized field (a plain string counts as English)."""
    if isinstance(value, str):
        return {"en": value}
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if isinstance(v, str)}
    return {}


def check_text(report, where, value, languages, required=False):
    """A localized field: must be a string or {language: string}, with English present."""
    if value is None:
        if required:
            report.error("%s is missing" % where)
        return
    if not isinstance(value, (str, dict)) or (isinstance(value, dict) and any(not isinstance(v, str) for v in value.values())):
        report.error("%s must be text or an object of language: text" % where)
        return
    found = texts(value)
    if not found.get("en", "").strip():
        report.error("%s has no English text" % where)
        return
    for language in languages:
        if language != "en" and not found.get(language, "").strip():
            report.warning("%s has no \"%s\" translation (English will be shown)" % (where, language))
    for language, text in found.items():
        if SOURCE_NAMES.search(text):
            report.error("%s (%s) mentions a source or a URL; that text is shown to players" % (where, language))
        for tag, body in MARKUP.findall(text):
            if tag not in ("p", "l", "i"):
                report.warning("%s (%s) uses unknown markup {%s:...}; it will be shown as plain text" % (where, language, tag))
            elif not body.strip():
                report.error("%s (%s) has an empty {%s:} tag" % (where, language, tag))
        if text.count("{") != text.count("}"):
            report.warning("%s (%s) has unbalanced braces" % (where, language))


def check_pin(report, where, pin, land):
    if pin is None:
        return
    if not isinstance(pin, dict) or not all(isinstance(pin.get(k), (int, float)) and not isinstance(pin.get(k), bool) for k in "xy"):
        report.error("%s must be { \"x\": number, \"y\": number }" % where)
        return
    if not (0 <= pin["x"] <= 1 and 0 <= pin["y"] <= 1):
        report.error("%s is outside 0 to 1 (%s, %s)" % (where, pin["x"], pin["y"]))
    elif land is not None and not land((pin["x"], pin["y"])):
        report.warning("%s (%s, %s) is in the water on our map" % (where, pin["x"], pin["y"]))


def duplicates(ids):
    seen, repeated = set(), []
    for ident in ids:
        if ident in seen and ident not in repeated:
            repeated.append(ident)
        seen.add(ident)
    return repeated


def land_test():
    """Point-on-land test against our own map, if it has been generated."""
    path = os.path.join(ROOT, "LeonidaMissions", "Resources", "map.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    def inside(point, polygon):
        x, y = point
        hit = False
        for i, a in enumerate(polygon):
            b = polygon[i - 1]
            if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                hit = not hit
        return hit

    return lambda point: (any(inside(point, s["points"]) for s in data["land"])
                          and not any(inside(point, s["points"]) for s in data["lakes"]))


def validate(content, languages=("en",)):
    report = Report()
    if not isinstance(content, dict):
        report.error("the file must be a JSON object")
        return report
    land = land_test()

    version = content.get("contentVersion")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        report.error("contentVersion must be a whole number, 1 or higher")
    for key in ("chapters", "missions", "trackerCategories", "trackerItems", "regions", "news", "credits"):
        if key in content and not isinstance(content[key], list):
            report.error("\"%s\" must be a list" % key)
            content[key] = []
    chapters = content.get("chapters", [])
    missions = content.get("missions", [])
    categories = content.get("trackerCategories", [])
    items = content.get("trackerItems", [])
    regions = content.get("regions", [])
    if not chapters:
        report.error("no chapters")
    if not missions:
        report.error("no missions")

    for kind, entries in (("chapter", chapters), ("mission", missions), ("tracker category", categories),
                          ("tracker item", items), ("region", regions), ("news", content.get("news", []))):
        ids = [e.get("id") if isinstance(e, dict) else None for e in entries]
        if any(not isinstance(i, str) or not i for i in ids):
            report.error("a %s has no id" % kind)
        for ident in duplicates([i for i in ids if isinstance(i, str)]):
            report.error("duplicate %s id \"%s\"" % (kind, ident))

    chapter_ids = {c.get("id") for c in chapters if isinstance(c, dict)}
    mission_ids = {m.get("id") for m in missions if isinstance(m, dict)}
    category_ids = {c.get("id") for c in categories if isinstance(c, dict)}
    region_ids = {r.get("id") for r in regions if isinstance(r, dict)}

    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        check_text(report, "chapter \"%s\" title" % chapter.get("id"), chapter.get("title"), languages, required=True)
        if not isinstance(chapter.get("order"), int):
            report.error("chapter \"%s\" needs a whole-number order" % chapter.get("id"))

    for mission in missions:
        if not isinstance(mission, dict):
            report.error("a mission is not an object")
            continue
        name = "mission \"%s\"" % mission.get("id")
        check_text(report, name + " title", mission.get("title"), languages, required=True)
        for field in ("summary", "unlock", "missableNote"):
            check_text(report, "%s %s" % (name, field), mission.get(field), languages)
        mission_type = mission.get("type", "story")
        if mission_type not in MISSION_TYPES:
            report.warning("%s has unknown type \"%s\" (shown as Other)" % (name, mission_type))
        if mission.get("chapterId") is not None and mission.get("chapterId") not in chapter_ids:
            report.error("%s refers to unknown chapter \"%s\"" % (name, mission.get("chapterId")))
        if mission_type == "story" and mission.get("chapterId") is None:
            report.error("%s is a story mission without a chapter" % name)
        if mission.get("parentId") is not None and mission.get("parentId") not in mission_ids:
            report.error("%s refers to unknown parent \"%s\"" % (name, mission.get("parentId")))
        if mission.get("character") is not None and mission.get("character") not in CHARACTERS:
            report.warning("%s has unknown character \"%s\" (ignored)" % (name, mission.get("character")))
        heat = mission.get("heat")
        if heat is not None and (isinstance(heat, bool) or not isinstance(heat, int) or not 0 <= heat <= 5):
            report.error("%s has heat %r, expected a whole number from 0 to 5" % (name, heat))
        spoiler = mission.get("spoilerLevel", 0)
        if isinstance(spoiler, bool) or not isinstance(spoiler, int) or not 0 <= spoiler <= 2:
            report.error("%s has spoilerLevel %r, expected 0, 1 or 2" % (name, spoiler))
        minutes = mission.get("estimatedMinutes")
        if minutes is not None and (isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 0):
            report.error("%s has a bad estimatedMinutes" % name)
        step_ids = []
        for group in ("steps", "bonusObjectives"):
            for step in mission.get(group, []) or []:
                if not isinstance(step, dict) or not isinstance(step.get("id"), str):
                    report.error("%s has a step without an id in %s" % (name, group))
                    continue
                step_ids.append(step["id"])
                check_text(report, "%s step \"%s\"" % (name, step["id"]), step.get("text"), languages, required=True)
        for ident in duplicates(step_ids):
            report.error("%s has duplicate step id \"%s\"" % (name, ident))
        for index, tip in enumerate(mission.get("tips", []) or []):
            check_text(report, "%s tip %d" % (name, index + 1), tip, languages, required=True)
        for index, hint in enumerate(mission.get("controls", []) or []):
            if not isinstance(hint, dict) or not all(isinstance(hint.get(k), str) and hint.get(k) for k in ("ps5", "xbox")):
                report.error("%s control %d needs \"ps5\" and \"xbox\" labels" % (name, index + 1))
            else:
                check_text(report, "%s control %d action" % (name, index + 1), hint.get("action"), languages, required=True)
        rewards = mission.get("rewards") or {}
        money = rewards.get("money") if isinstance(rewards, dict) else None
        if money is not None and (isinstance(money, bool) or not isinstance(money, int)):
            report.error("%s rewards.money must be a whole number or null" % name)
        for index, unlock in enumerate((rewards.get("unlocks") if isinstance(rewards, dict) else None) or []):
            check_text(report, "%s reward %d" % (name, index + 1), unlock, languages, required=True)
        check_pin(report, name + " mapPin", mission.get("mapPin"), land)
        if mission.get("region") is not None and mission.get("region") not in region_ids:
            report.warning("%s refers to unknown region \"%s\"" % (name, mission.get("region")))
        sources = mission.get("sources", []) or []
        if mission.get("verified") and len(sources) < 2:
            report.warning("%s is marked verified with fewer than two sources" % name)

    for category in categories:
        if not isinstance(category, dict):
            continue
        name = "tracker category \"%s\"" % category.get("id")
        check_text(report, name + " title", category.get("title"), languages, required=True)
        check_text(report, name + " summary", category.get("summary"), languages)
        if category.get("kind") not in TRACKER_KINDS:
            report.warning("%s has unknown kind \"%s\" (shown under More lists)" % (name, category.get("kind")))
        if category.get("color") is not None and category.get("color") not in COLOURS:
            report.warning("%s has unknown colour \"%s\" (pink is used)" % (name, category.get("color")))
        weight = category.get("weightIn100", 0)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight < 0:
            report.error("%s has a bad weightIn100" % name)
        if category.get("platform") not in (None, "ps5", "xbox"):
            report.warning("%s has unknown platform \"%s\"" % (name, category.get("platform")))

    for item in items:
        if not isinstance(item, dict):
            report.error("a tracker item is not an object")
            continue
        name = "tracker item \"%s\"" % item.get("id")
        check_text(report, name + " title", item.get("title"), languages, required=True)
        check_text(report, name + " description", item.get("description"), languages)
        if item.get("categoryId") not in category_ids:
            report.error("%s refers to unknown category \"%s\"" % (name, item.get("categoryId")))
        check_pin(report, name + " mapPin", item.get("mapPin"), land)
        spoiler = item.get("spoilerLevel", 0)
        if isinstance(spoiler, bool) or not isinstance(spoiler, int) or not 0 <= spoiler <= 2:
            report.error("%s has spoilerLevel %r, expected 0, 1 or 2" % (name, spoiler))
        if item.get("region") is not None and item.get("region") not in region_ids:
            report.warning("%s refers to unknown region \"%s\"" % (name, item.get("region")))

    for region in regions:
        if not isinstance(region, dict):
            continue
        check_text(report, "region \"%s\" title" % region.get("id"), region.get("title"), languages, required=True)
        centre = region.get("center")
        if not isinstance(centre, dict) or not all(isinstance(centre.get(k), (int, float)) for k in "xy") \
                or not (0 <= centre["x"] <= 1 and 0 <= centre["y"] <= 1):
            report.error("region \"%s\" needs a center inside 0 to 1" % region.get("id"))

    for entry in content.get("news", []):
        if isinstance(entry, dict):
            check_text(report, "news \"%s\" title" % entry.get("id"), entry.get("title"), languages, required=True)
            check_text(report, "news \"%s\" body" % entry.get("id"), entry.get("body"), languages, required=True)
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(entry.get("date", ""))):
                report.error("news \"%s\" needs a date like 2026-11-27" % entry.get("id"))

    weights = (content.get("completion") or {}).get("missionWeights", {})
    if not isinstance(weights, dict):
        report.error("completion.missionWeights must be an object")
    else:
        for key, weight in weights.items():
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight < 0:
                report.error("completion weight for \"%s\" must be a number, 0 or higher" % key)
            if key not in MISSION_TYPES:
                report.warning("completion weight for unknown mission type \"%s\"" % key)

    for credit in content.get("credits", []):
        if not isinstance(credit, dict) or not all(isinstance(credit.get(k), str) and credit.get(k) for k in ("id", "title", "url", "license")):
            report.error("every credit needs id, title, url and license")
    return report


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        print(__doc__)
        return 2
    languages = ["en"]
    manifest_path = None
    if "--languages" in args:
        languages = args[args.index("--languages") + 1].split(",")
    if "--manifest" in args:
        manifest_path = args[args.index("--manifest") + 1]
    try:
        with open(args[0], encoding="utf-8") as f:
            content = json.load(f)
    except (OSError, ValueError) as error:
        print("ERROR: cannot read %s as JSON: %s" % (args[0], error))
        return 1

    report = validate(content, languages)
    if manifest_path:
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            if manifest.get("contentVersion") != content.get("contentVersion"):
                report.error("manifest.json says contentVersion %r but content.json has %r"
                             % (manifest.get("contentVersion"), content.get("contentVersion")))
        except (OSError, ValueError) as error:
            report.error("cannot read the manifest: %s" % error)

    limit = 60
    for message in report.warnings[:limit]:
        print("warning:", message)
    if len(report.warnings) > limit:
        print("warning: ... and %d more warnings" % (len(report.warnings) - limit))
    for message in report.errors:
        print("ERROR:", message)
    print("%s: %d error(s), %d warning(s); %d missions, %d tracker items"
          % (args[0], len(report.errors), len(report.warnings),
             len(content.get("missions", [])) if isinstance(content, dict) else 0,
             len(content.get("trackerItems", [])) if isinstance(content, dict) else 0))
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
