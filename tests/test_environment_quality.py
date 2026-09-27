import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from edit_prompt import build_edit_prompt
from prompt_builder import build_prompt, load_monster_spec
from quality_system import environment_approval_checks, environment_directives


class EnvironmentQualityTests(unittest.TestCase):
    def setUp(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        self.goblin_page = next(page for page in tome["pages"] if page["page_id"] == "I-03")

    def test_global_environment_standard_is_in_generation_prompt(self):
        text = build_prompt(self.goblin_page)
        self.assertIn("GLOBAL ENVIRONMENT STANDARD", text)
        self.assertIn("two to four large", text)
        self.assertIn("named habitat unmistakable", text)
        self.assertIn("creature remains primary", text)

    def test_environment_is_preserved_during_image_edit(self):
        text = build_edit_prompt(
            self.goblin_page,
            {"quick_tags": ["environment generic"], "text": "make the pantry dungeon-specific"},
        )
        self.assertIn("ENVIRONMENT PRESERVATION RULE", text)
        self.assertIn("Replace generic room or backdrop details", text)
        self.assertIn("dungeon-specific", text)

    def test_goblin_identity_rejects_imp_furry_and_elf_drift(self):
        spec = load_monster_spec(self.goblin_page)
        visual = spec["visual_identity"]
        avoid = " ".join(visual["must_avoid"]).lower()
        self.assertIn("elf-child", avoid)
        self.assertIn("imp", avoid)
        self.assertIn("furry", avoid)
        self.assertIn("broad flattened", visual["head_features"].lower())

    def test_goblin_pantry_rejects_modern_domestic_drift(self):
        avoid = " ".join(self.goblin_page["must_avoid"]).lower()
        self.assertIn("modern household", avoid)
        self.assertIn("generic pantry", avoid)
        self.assertTrue(any("stone" in item.lower() for item in self.goblin_page["must_include"]))

    def test_environment_review_checks_exist(self):
        directives = environment_directives(ROOT)
        checks = environment_approval_checks(ROOT)
        self.assertGreaterEqual(len(directives), 6)
        self.assertGreaterEqual(len(checks), 5)


if __name__ == "__main__":
    unittest.main()
