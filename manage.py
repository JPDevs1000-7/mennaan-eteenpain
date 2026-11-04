#!/usr/bin/env python3
"""Admin CLI for weekly content (UC-6). Standard library only.

  python manage.py new-week --week 2026-W47 --theme "Gratitude"   # prompts for 7 questions
  python manage.py validate                                       # used by CI
  python manage.py manifest                                       # rebuild content/manifest.json

Translation uses the Anthropic API when ANTHROPIC_API_KEY is set. Without a key, or with
--no-translate, missing languages get a "TODO" placeholder that `validate` rejects, so
untranslated content can never be published by accident.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
WEEKS = CONTENT / "weeks"
MANIFEST = CONTENT / "manifest.json"
WEEK_RE = re.compile(r"(\d{4})-W(0[1-9]|[1-4]\d|5[0-3])")
PLACEHOLDER = "TODO"
QUESTIONS_PER_WEEK = 7
MODEL = "claude-sonnet-5-5"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iso_weeks_in_year(year):
    """Number of ISO weeks (52 or 53) in a year."""
    return datetime.date(year, 12, 28).isocalendar()[1]


def valid_week_id(week_id):
    m = WEEK_RE.fullmatch(week_id) if isinstance(week_id, str) else None
    return bool(m) and int(m.group(2)) <= iso_weeks_in_year(int(m.group(1)))


def text_of(entry):
    """The 'text' of a {'text': ...} entry, or '' if the entry is malformed."""
    value = entry.get("text", "") if isinstance(entry, dict) else ""
    return value.strip() if isinstance(value, str) else ""


def check_text(label, text, errors):
    if not text:
        errors.append(f"{label}: missing text")
    elif text.startswith(PLACEHOLDER):
        errors.append(f"{label}: text is still a placeholder")


def validate_week(data, languages, name="week"):
    """Return a list of human-readable problems (empty list = valid). Never raises on bad content."""
    errors = []
    if not isinstance(data, dict):
        return [f"{name}: top level must be an object"]
    week_id = data.get("week_id", "")
    if not valid_week_id(week_id):
        errors.append(f"{name}: invalid week_id {week_id!r}")
    theme = data.get("theme")
    if not isinstance(theme, dict):
        errors.append(f"{name}: theme must be an object with one text per language")
        theme = {}
    for lang in languages:
        value = theme.get(lang, "")
        check_text(f"{name} theme.{lang}", value.strip() if isinstance(value, str) else "", errors)
    questions = data.get("questions", [])
    if not isinstance(questions, list):
        return errors + [f"{name}: questions must be a list"]
    if len(questions) != QUESTIONS_PER_WEEK:
        errors.append(f"{name}: expected {QUESTIONS_PER_WEEK} questions, found {len(questions)}")
    seen_days, seen_ids = set(), set()
    for q in questions:
        if not isinstance(q, dict):
            errors.append(f"{name}: every question must be an object")
            continue
        day, qid = q.get("day_of_week"), q.get("id", "")
        if type(day) is not int or day not in range(1, 8) or day in seen_days:
            errors.append(f"{name}: bad or duplicate day_of_week {day!r}")
        else:
            seen_days.add(day)
        expected_id = f"q-{str(week_id).lower()}-{day}"
        if qid != expected_id or qid in seen_ids:
            errors.append(f"{name}: id {qid!r} should be {expected_id!r} and unique")
        seen_ids.add(qid)
        translations = q.get("translations", {})
        translations = translations if isinstance(translations, dict) else {}
        for lang in languages:
            check_text(f"{qid} {lang}", text_of(translations.get(lang)), errors)
    return errors


def validate_all(content_dir=CONTENT):
    content_dir = Path(content_dir)
    manifest = load_json(content_dir / "manifest.json")
    languages = manifest["languages"]
    errors = []
    on_disk = sorted(p.stem for p in (content_dir / "weeks").glob("*.json"))
    if sorted(manifest["weeks"]) != on_disk:
        errors.append(f"manifest weeks {sorted(manifest['weeks'])} do not match files {on_disk}; run `manifest`")
    for week_id in on_disk:
        try:
            data = load_json(content_dir / "weeks" / f"{week_id}.json")
        except (OSError, ValueError) as exc:
            errors.append(f"{week_id}.json: cannot be read as JSON ({exc})")
            continue
        if isinstance(data, dict) and data.get("week_id") != week_id:
            errors.append(f"{week_id}.json: week_id does not match file name")
        errors += validate_week(data, languages, name=f"{week_id}.json")
    return errors


def rebuild_manifest():
    manifest = load_json(MANIFEST)
    manifest["weeks"] = sorted(p.stem for p in WEEKS.glob("*.json"))
    write_json(MANIFEST, manifest)
    return manifest


def translate(texts, source, targets):
    """Translate texts with the Anthropic API. Returns {lang: [texts]}, or None when no API key is set.

    Raises TranslationError for any failure (network, HTTP, bad reply) so the caller can fall back.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    prompt = (
        f"Translate these {len(texts)} short texts from '{source}' into the language codes "
        f"{targets}. Keep the warm, natural tone. Reply with ONLY a JSON object mapping each language code "
        f"to a list of {len(texts)} strings in the same order.\n\n" + json.dumps(texts, ensure_ascii=False)
    )
    body = json.dumps({"model": MODEL, "max_tokens": 4000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            reply = json.load(resp)["content"][0]["text"]
        result = json.loads(reply[reply.index("{"): reply.rindex("}") + 1])
        for lang in targets:
            items = result.get(lang)
            if not isinstance(items, list) or len(items) != len(texts):
                raise ValueError(f"translation for {lang} has the wrong number of items")
            if not all(isinstance(item, str) and item.strip() for item in items):
                raise ValueError(f"translation for {lang} contains an empty or non-text item")
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:  # URLError and HTTPError are OSError
        raise TranslationError(str(exc)) from exc
    return result


class TranslationError(Exception):
    pass


def cmd_new_week(args):
    if not valid_week_id(args.week):
        sys.exit(f"Invalid --week {args.week!r}; expected a real ISO week such as 2026-W34")
    path = WEEKS / f"{args.week}.json"
    if path.exists() and not args.force:
        sys.exit(f"{path.name} already exists (use --force to overwrite)")
    manifest = load_json(MANIFEST)
    languages = manifest["languages"]
    if args.primary not in languages:
        sys.exit(f"--primary must be one of {languages}")
    if not args.theme.strip():
        sys.exit("--theme must not be empty")
    texts = args.prompt or [input(f"Prompt {i} ({args.primary}): ").strip()
                            for i in range(1, QUESTIONS_PER_WEEK + 1)]
    if len(texts) != QUESTIONS_PER_WEEK or not all(texts):
        sys.exit(f"Exactly {QUESTIONS_PER_WEEK} non-empty prompts are required")
    others = [lang for lang in languages if lang != args.primary]
    translated = None
    if others and not args.no_translate:
        try:
            # The theme is translated together with the prompts (it is the last item).
            translated = translate([*texts, args.theme.strip()], args.primary, others)
        except TranslationError as exc:
            print(f"Translation failed ({exc}).")
    if others and translated is None:
        print("No translation performed: placeholders written. Edit them before validating.")

    def tr(lang, i):  # i indexes the texts list; the theme sits at index QUESTIONS_PER_WEEK
        return translated[lang][i] if translated else f"{PLACEHOLDER}: translate to {lang}"

    theme = {args.primary: args.theme.strip(), **{lang: tr(lang, QUESTIONS_PER_WEEK) for lang in others}}
    questions = []
    for i, text in enumerate(texts):
        translations = {args.primary: {"text": text}, **{lang: {"text": tr(lang, i)} for lang in others}}
        questions.append({"day_of_week": i + 1, "id": f"q-{args.week.lower()}-{i + 1}", "translations": translations})
    write_json(path, {"week_id": args.week, "theme": theme, "questions": questions})
    rebuild_manifest()
    print(f"Wrote {path.relative_to(ROOT)}. Review it, run `python manage.py validate`, then git commit and push.")


def cmd_validate(_args):
    errors = validate_all()
    for e in errors:
        print("ERROR:", e)
    if errors:
        sys.exit(1)
    print("Content OK")


def cmd_manifest(_args):
    print(json.dumps(rebuild_manifest(), indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    nw = sub.add_parser("new-week", help="create a week of prompts")
    nw.add_argument("--week", required=True)
    nw.add_argument("--theme", required=True, help="theme in the primary language; it is translated too")
    nw.add_argument("--primary", default="fi", help="language the prompts are written in")
    nw.add_argument("--prompt", action="append", help="repeat 7 times instead of typing interactively")
    nw.add_argument("--no-translate", action="store_true")
    nw.add_argument("--force", action="store_true")
    nw.set_defaults(func=cmd_new_week)
    sub.add_parser("validate", help="check all content").set_defaults(func=cmd_validate)
    sub.add_parser("manifest", help="rebuild content/manifest.json").set_defaults(func=cmd_manifest)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
