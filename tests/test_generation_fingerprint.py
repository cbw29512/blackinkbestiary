import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "art_pipeline" / "generation_fingerprint.py"
spec = importlib.util.spec_from_file_location("generation_fingerprint", SCRIPT)
fingerprint = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(fingerprint)


class GenerationFingerprintTests(unittest.TestCase):
    def _page(self):
        return {
            "page_id": "I-01",
            "monster_spec_id": "kobold-warrior",
            "archetype": "trap_scene",
            "environment_profile_id": "underground.trapped-stone-corridor",
            "environment_variant": {"landmark": "pit", "framing": "corridor", "interaction": "tripwire"},
            "physicality": {"mode": "grounded", "support": "floor", "motion": "lean"},
            "moment": "triggering a tripwire",
            "identity_rules": ["small reptilian humanoid"],
            "must_include": ["pit"],
            "must_avoid": [],
        }

    def test_generation_authority_change_changes_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config").mkdir(parents=True)
            path = root / "config" / "coloring_page_standard.json"
            path.write_text('{"version": 1}', encoding="utf-8")
            first = fingerprint.page_generation_fingerprint(self._page(), root)
            path.write_text('{"version": 2}', encoding="utf-8")
            second = fingerprint.page_generation_fingerprint(self._page(), root)
            self.assertNotEqual(first, second)

    def test_reviewer_change_does_not_force_rerender_but_changes_review_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "art_pipeline").mkdir(parents=True)
            reviewer = root / "art_pipeline" / "vision_review_prompts.py"
            reviewer.write_text("version = 1", encoding="utf-8")

            first_generation = fingerprint.page_generation_fingerprint(self._page(), root)
            first_review = fingerprint.page_review_fingerprint(self._page(), root)

            reviewer.write_text("version = 2", encoding="utf-8")

            second_generation = fingerprint.page_generation_fingerprint(self._page(), root)
            second_review = fingerprint.page_review_fingerprint(self._page(), root)

            self.assertEqual(first_generation, second_generation)
            self.assertNotEqual(first_review, second_review)

    def test_page_identity_rule_change_changes_generation_fingerprint(self):
        first_page = self._page()
        second_page = self._page()
        second_page["identity_rules"] = ["one continuous non-humanoid mantle body"]

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = fingerprint.page_generation_fingerprint(first_page, root)
            second = fingerprint.page_generation_fingerprint(second_page, root)

        self.assertNotEqual(first, second)

    def test_unrelated_document_change_does_not_change_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config").mkdir(parents=True)
            (root / "config" / "coloring_page_standard.json").write_text(
                '{"version": 1}', encoding="utf-8"
            )
            first = fingerprint.page_generation_fingerprint(self._page(), root)
            (root / "README.md").write_text("first", encoding="utf-8")
            second = fingerprint.page_generation_fingerprint(self._page(), root)
            (root / "README.md").write_text("second", encoding="utf-8")
            third = fingerprint.page_generation_fingerprint(self._page(), root)
            self.assertEqual(first, second)
            self.assertEqual(second, third)


if __name__ == "__main__":
    unittest.main()
