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
WEEK_RE = re.compile(r"^(\d{4})-W(0[1-9]|[1-4]\d|5[0-3])$")
PLACEHOLDER = "TODO"
QUESTIONS_PER_WEEK = 7
MODEL = "claude-sonnet-5-5"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_week(data, languages, name="week"):
    """Return a list of human-readable problems (empty list = valid)."""
    errors = []
    week_id = data.get("week_id", "")
    if not WEEK_RE.match(str(week_id)):
        errors.append(f"{name}: invalid week_id {week_id!r}")
    if not str(data.get("theme", "")).strip():
        errors.append(f"{name}: missing theme")
    questions = data.get("questions", [])
    if len(questions) != QUESTIONS_PER_WEEK:
        errors.append(f"{name}: expected {QUESTIONS_PER_WEEK} questions, found {len(questions)}")
    seen_days, seen_ids = set(), set()
    for q in questions:
        day, qid = q.get("day_of_week"), q.get("id", "")
        if day not in range(1, 8) or day in seen_days:
            errors.append(f"{name}: bad or duplicate day_of_week {day!r}")
        seen_days.add(day)
        expected_id = f"q-{str(week_id).lower()}-{day}"
        if qid != expected_id or qid in seen_ids:
            errors.append(f"{name}: id {qid!r} should be {expected_id!r} and unique")
        seen_ids.add(qid)
        for lang in languages:
            text = str(q.get("translations", {}).get(lang, {}).get("text", "")).strip()
            if not text:
                errors.append(f"{qid}: missing {lang} text")
            elif text.startswith(PLACEHOLDER):
                errors.append(f"{qid}: {lang} text is still a placeholder")
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
        data = load_json(content_dir / "weeks" / f"{week_id}.json")
        if data.get("week_id") != week_id:
            errors.append(f"{week_id}.json: week_id does not match file name")
        errors += validate_week(data, languages, name=f"{week_id}.json")
    return errors


def rebuild_manifest():
    manifest = load_json(MANIFEST)
    manifest["weeks"] = sorted(p.stem for p in WEEKS.glob("*.json"))
    write_json(MANIFEST, manifest)
    return manifest


def translate(texts, source, targets):
    """Translate a list of texts with the Anthropic API. Returns {lang: [texts]} or None."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    prompt = (
        f"Translate these {len(texts)} couple-conversation prompts from '{source}' into the language codes "
        f"{targets}. Keep the warm, natural tone. Reply with ONLY a JSON object mapping each language code "
        f"to a list of {len(texts)} strings in the same order.\n\n" + json.dumps(texts, ensure_ascii=False)
    )
    body = json.dumps({"model": MODEL, "max_tokens": 4000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        reply = json.load(resp)["content"][0]["text"]
    result = json.loads(reply[reply.index("{"): reply.rindex("}") + 1])
    for lang in targets:
        if len(result.get(lang, [])) != len(texts):
            raise ValueError(f"translation for {lang} has the wrong number of items")
    return result


def cmd_new_week(args):
    if not WEEK_RE.match(args.week):
        sys.exit(f"Invalid --week {args.week!r}; expected e.g. 2026-W34")
    path = WEEKS / f"{args.week}.json"
    if path.exists() and not args.force:
        sys.exit(f"{path.name} already exists (use --force to overwrite)")
    manifest = load_json(MANIFEST)
    languages = manifest["languages"]
    if args.primary not in languages:
        sys.exit(f"--primary must be one of {languages}")
    texts = args.prompt or [input(f"Prompt {i} ({args.primary}): ").strip()
                            for i in range(1, QUESTIONS_PER_WEEK + 1)]
    if len(texts) != QUESTIONS_PER_WEEK or not all(texts):
        sys.exit(f"Exactly {QUESTIONS_PER_WEEK} non-empty prompts are required")
    others = [lang for lang in languages if lang != args.primary]
    translated = None if args.no_translate else translate(texts, args.primary, others)
    if translated is None and others:
        print("No translation performed: placeholders written. Edit them before validating.")
    questions = []
    for i, text in enumerate(texts, start=1):
        tr = {args.primary: {"text": text}}
        for lang in others:
            tr[lang] = {"text": translated[lang][i - 1] if translated else f"{PLACEHOLDER}: translate to {lang}"}
        questions.append({"day_of_week": i, "id": f"q-{args.week.lower()}-{i}", "translations": tr})
    write_json(path, {"week_id": args.week, "theme": args.theme, "questions": questions})
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
    nw.add_argument("--theme", required=True)
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
