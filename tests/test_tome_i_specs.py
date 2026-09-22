import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from prompt_builder import load_monster_spec


class TomeISpecTests(unittest.TestCase):
    def test_every_page_has_complete_canonical_spec(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        self.assertEqual(len(tome["pages"]), 50)

        required_visual = {
            "core_identity",
            "silhouette",
            "head_features",
            "body_shape",
            "surface",
            "signature_gear",
            "attitude",
            "must_keep",
            "must_avoid",
        }

        for page in tome["pages"]:
            self.assertTrue(page.get("monster_spec_id"), page["page_id"])
            spec = load_monster_spec(page)
            self.assertEqual(spec["monster_id"], page["monster_spec_id"])
            self.assertEqual(spec["monster_name"], page["monster_name"])
            self.assertTrue(required_visual.issubset(spec["visual_identity"]))
            self.assertTrue(spec["visual_identity"]["must_keep"])
            self.assertTrue(spec["visual_identity"]["must_avoid"])
            self.assertTrue(spec["accuracy_checks"])
            self.assertTrue(page["must_include"])

    def test_every_page_uses_monster_first_visual_hierarchy(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        for page in tome["pages"]:
            composition = page.get("composition", "").lower()
            self.assertIn("large centered or near-centered dominant focal subject", composition, page["page_id"])
            self.assertIn("55–72% of page height", page.get("composition", ""), page["page_id"])
            self.assertIn("two to four large supporting forms", composition, page["page_id"])

    def test_page_requirements_are_concrete(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        forbidden_placeholders = {"one clear story moment", "large open areas to color"}

        for page in tome["pages"]:
            requirements = {item.lower() for item in page["must_include"]}
            self.assertFalse(
                requirements.intersection(forbidden_placeholders),
                f"{page['page_id']} still has placeholder requirements",
            )
            self.assertGreaterEqual(len(requirements), 4, page["page_id"])


if __name__ == "__main__":
    unittest.main()
