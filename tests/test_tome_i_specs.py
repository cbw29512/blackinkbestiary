import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from page_contract import resolve_page_spec
from prompt_builder import load_monster_spec


class TomeISpecTests(unittest.TestCase):
    def setUp(self):
        self.tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))

    def test_tome_i_is_minimal_page_v2(self):
        self.assertEqual(self.tome["page_contract"], "black-ink-page-v2")
        self.assertEqual(len(self.tome["pages"]), 50)
        allowed = {
            "page_id",
            "order",
            "monster_spec_id",
            "environment_profile_id",
            "moment",
            "archetype",
            "environment_variant",
            "physicality",
            "page_exceptions",
        }
        for page in self.tome["pages"]:
            self.assertTrue(set(page).issubset(allowed), page["page_id"])
            self.assertNotIn("monster_name", page, page["page_id"])
            self.assertNotIn("habitat", page, page["page_id"])
            self.assertNotIn("identity_rules", page, page["page_id"])
            self.assertNotIn("must_include", page, page["page_id"])
            self.assertNotIn("must_avoid", page, page["page_id"])
            self.assertNotIn("coloring_rules", page, page["page_id"])
            self.assertNotIn("reference_image", page, page["page_id"])
            self.assertNotIn("modify", page, page["page_id"])

    def test_every_page_resolves_complete_canonical_monster(self):
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
        for page in self.tome["pages"]:
            spec = load_monster_spec(page)
            resolved = resolve_page_spec(page, ROOT)
            self.assertEqual(spec["monster_id"], page["monster_spec_id"])
            self.assertEqual(spec["monster_name"], resolved["monster_name"])
            self.assertTrue(required_visual.issubset(spec["visual_identity"]))
            self.assertTrue(spec["visual_identity"]["must_keep"])
            self.assertTrue(spec["visual_identity"]["must_avoid"])
            self.assertTrue(spec["accuracy_checks"])

    def test_every_page_uses_universal_visual_hierarchy(self):
        for page in self.tome["pages"]:
            resolved = resolve_page_spec(page, ROOT)
            composition = resolved["composition"].lower()
            self.assertIn("large centered or near-centered dominant focal subject", composition, page["page_id"])
            self.assertIn("60–75% of page height", resolved["composition"], page["page_id"])
            self.assertIn("two to four large supporting forms", composition, page["page_id"])

    def test_every_page_has_complete_unique_scene_recipe(self):
        for page in self.tome["pages"]:
            variant = page.get("environment_variant") or {}
            physicality = page.get("physicality") or {}
            self.assertTrue(page.get("moment"), page["page_id"])
            self.assertTrue(page.get("archetype"), page["page_id"])
            self.assertTrue(variant.get("landmark"), page["page_id"])
            self.assertTrue(variant.get("framing"), page["page_id"])
            self.assertTrue(variant.get("interaction"), page["page_id"])
            self.assertTrue(physicality.get("mode"), page["page_id"])
            self.assertTrue(physicality.get("support"), page["page_id"])
            self.assertTrue(physicality.get("motion"), page["page_id"])


if __name__ == "__main__":
    unittest.main()
