import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from prompt_builder import load_monster_spec
from page_contract import missing_required_paths, resolve_page_spec


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
            resolved = resolve_page_spec(page, ROOT)
            self.assertEqual(spec["monster_name"], resolved["monster_name"])
            self.assertTrue(required_visual.issubset(spec["visual_identity"]))
            self.assertTrue(spec["visual_identity"]["must_keep"])
            self.assertTrue(spec["visual_identity"]["must_avoid"])
            self.assertTrue(spec["accuracy_checks"])

    def test_every_page_uses_monster_first_visual_hierarchy(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        for page in tome["pages"]:
            resolved = resolve_page_spec(page, ROOT)
            composition = resolved.get("composition", "").lower()
            self.assertIn("large centered or near-centered dominant focal subject", composition, page["page_id"])
            self.assertIn("60–75% of page height", resolved.get("composition", ""), page["page_id"])
            self.assertIn("two to four large supporting forms", composition, page["page_id"])
            self.assertNotIn("composition", page, page["page_id"])

    def test_every_page_has_explicit_physicality(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        for page in tome["pages"]:
            physicality = page.get("physicality") or {}
            self.assertTrue(physicality.get("mode"), page["page_id"])
            self.assertTrue(physicality.get("support"), page["page_id"])
            self.assertTrue(physicality.get("motion"), page["page_id"])

    def test_every_page_has_complete_unique_recipe(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        for page in tome["pages"]:
            self.assertEqual(missing_required_paths(page, ROOT), [], page["page_id"])


if __name__ == "__main__":
    unittest.main()
