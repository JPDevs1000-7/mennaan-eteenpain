import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import manage  # noqa: E402

LANGS = ["fi", "en"]


def good_week():
    return {
        "week_id": "2026-W50",
        "theme": "Test",
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
        self.assertTrue(any("missing en" in e for e in manage.validate_week(w, LANGS)))

    def test_placeholder_fails(self):
        w = good_week()
        w["questions"][0]["translations"]["en"]["text"] = "TODO: translate to en"
        self.assertTrue(any("placeholder" in e for e in manage.validate_week(w, LANGS)))

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


class ShippedContent(unittest.TestCase):
    def test_repository_content_is_valid(self):
        self.assertEqual(manage.validate_all(), [])

    def test_manifest_languages_match_app(self):
        manifest = json.loads((ROOT / "content" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["languages"], LANGS)


if __name__ == "__main__":
    unittest.main()
