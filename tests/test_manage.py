import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import manage  # noqa: E402

LANGS = ["fi", "en"]


def good_week():
    return {
        "week_id": "2026-W50",
        "theme": {"fi": "Teema", "en": "Theme"},
        "questions": [
            {"day_of_week": d, "id": f"q-2026-w50-{d}",
             "translations": {"fi": {"text": f"fi {d}"}, "en": {"text": f"en {d}"}}}
            for d in range(1, 8)
        ],
    }


class ValidateWeek(unittest.TestCase):
    def test_valid_week_passes(self):
        self.assertEqual(manage.validate_week(good_week(), LANGS), [])

    def test_missing_translation_fails(self):
        w = good_week()
        del w["questions"][2]["translations"]["en"]
        self.assertTrue(any("q-2026-w50-3 en: missing" in e for e in manage.validate_week(w, LANGS)))

    def test_placeholder_fails(self):
        w = good_week()
        w["questions"][0]["translations"]["en"]["text"] = "TODO: translate to en"
        self.assertTrue(any("placeholder" in e for e in manage.validate_week(w, LANGS)))

    def test_theme_must_exist_in_every_language(self):
        w = good_week()
        del w["theme"]["fi"]
        self.assertTrue(any("theme.fi" in e for e in manage.validate_week(w, LANGS)))

    def test_old_single_string_theme_is_rejected(self):
        w = good_week()
        w["theme"] = "Expressing Appreciation"
        self.assertTrue(any("theme must be an object" in e for e in manage.validate_week(w, LANGS)))

    def test_wrong_count_bad_id_and_week(self):
        w = good_week()
        w["questions"].pop()
        w["questions"][0]["id"] = "wrong"
        w["week_id"] = "2026-W99"
        errors = manage.validate_week(w, LANGS)
        self.assertTrue(any("expected 7" in e for e in errors))
        self.assertTrue(any("should be" in e for e in errors))
        self.assertTrue(any("invalid week_id" in e for e in errors))

    def test_duplicate_day_fails(self):
        w = copy.deepcopy(good_week())
        w["questions"][1]["day_of_week"] = 1
        self.assertTrue(any("duplicate day" in e for e in manage.validate_week(w, LANGS)))

    def test_malformed_content_reports_errors_instead_of_raising(self):
        for mutate in (
            lambda w: w["questions"][0].update(day_of_week=[1]),
            lambda w: w["questions"][0].update(day_of_week=True),
            lambda w: w["questions"][0]["translations"].update(en="just a string"),
            lambda w: w["questions"].__setitem__(0, "not an object"),
            lambda w: w.update(questions="nope"),
            lambda w: w["theme"].update(en=5),
        ):
            w = good_week()
            mutate(w)
            self.assertTrue(manage.validate_week(w, LANGS), "expected at least one error")
        self.assertTrue(manage.validate_week([], LANGS))


class WeekIds(unittest.TestCase):
    def test_week_53_only_in_long_years(self):
        self.assertTrue(manage.valid_week_id("2026-W53"))   # 2026 has 53 ISO weeks
        self.assertFalse(manage.valid_week_id("2025-W53"))  # 2025 has 52
        self.assertTrue(manage.valid_week_id("2026-W01"))

    def test_rejects_junk_including_trailing_newline(self):
        for bad in ("2026-W34\n", "2026-W00", "2026-W54", "26-W34", "", None, 5):
            self.assertFalse(manage.valid_week_id(bad), repr(bad))


class NewWeek(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = Path(self.tmp.name)
        (tmp / "weeks").mkdir()
        (tmp / "manifest.json").write_text(json.dumps({"languages": LANGS, "weeks": []}), encoding="utf-8")
        patches = [mock.patch.object(manage, "CONTENT", tmp), mock.patch.object(manage, "WEEKS", tmp / "weeks"),
                   mock.patch.object(manage, "MANIFEST", tmp / "manifest.json"), mock.patch.object(manage, "ROOT", tmp)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.tmp_path = tmp

    def run_new_week(self, **env):
        argv = ["new-week", "--week", "2026-W47", "--theme", "Kiitollisuus"]
        for i in range(1, 8):
            argv += ["--prompt", f"Kysymys {i}"]
        with mock.patch.dict(os.environ, env, clear=False), contextlib.redirect_stdout(io.StringIO()) as out:
            manage.main(argv)
        return out.getvalue()

    def written(self):
        return json.loads((self.tmp_path / "weeks" / "2026-W47.json").read_text(encoding="utf-8"))

    def test_without_api_key_writes_placeholders_that_validation_rejects(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.run_new_week()
        data = self.written()
        self.assertEqual(data["theme"]["fi"], "Kiitollisuus")
        self.assertTrue(data["theme"]["en"].startswith("TODO"))
        self.assertTrue(manage.validate_week(data, LANGS))

    def test_api_failure_keeps_the_typed_prompts_and_does_not_crash(self):
        err = urllib.error.URLError("boom")
        with mock.patch("urllib.request.urlopen", side_effect=err):
            out = self.run_new_week(ANTHROPIC_API_KEY="test-key")
        self.assertIn("Translation failed", out)
        data = self.written()
        self.assertEqual(data["questions"][3]["translations"]["fi"]["text"], "Kysymys 4")
        self.assertTrue(data["questions"][3]["translations"]["en"]["text"].startswith("TODO"))

    def test_successful_translation_includes_the_theme(self):
        reply = {"en": [f"Question {i}" for i in range(1, 8)] + ["Gratitude"]}
        payload = json.dumps({"content": [{"text": json.dumps(reply)}]}).encode()
        fake = mock.MagicMock()
        fake.__enter__.return_value = io.BytesIO(payload)
        with mock.patch("urllib.request.urlopen", return_value=fake):
            self.run_new_week(ANTHROPIC_API_KEY="test-key")
        data = self.written()
        self.assertEqual(data["theme"], {"fi": "Kiitollisuus", "en": "Gratitude"})
        self.assertEqual(manage.validate_week(data, LANGS), [])

    def test_bad_translation_reply_falls_back(self):
        reply = {"en": ["only one"]}
        payload = json.dumps({"content": [{"text": json.dumps(reply)}]}).encode()
        fake = mock.MagicMock()
        fake.__enter__.return_value = io.BytesIO(payload)
        with mock.patch("urllib.request.urlopen", return_value=fake):
            out = self.run_new_week(ANTHROPIC_API_KEY="test-key")
        self.assertIn("Translation failed", out)


class ShippedContent(unittest.TestCase):
    def test_repository_content_is_valid(self):
        self.assertEqual(manage.validate_all(), [])

    def test_manifest_languages_match_app(self):
        manifest = json.loads((ROOT / "content" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["languages"], LANGS)


if __name__ == "__main__":
    unittest.main()
