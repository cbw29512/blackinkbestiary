import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from prompt_builder import load_monster_spec
from page_contract import resolve_page_spec
from vision_review_prompts import review_stage_errors


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
            self.assertTrue(page["must_include"])

    def test_page_recipes_do_not_override_canonical_identity_with_generic_boilerplate(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        forbidden = {
            "use clear fantasy-monster anatomy and a strong silhouette",
        }
        for page in tome["pages"]:
            raw_rules = {
                str(item).strip().lower()
                for item in page.get("identity_rules") or []
            }
            self.assertFalse(
                raw_rules.intersection(forbidden),
                f"{page['page_id']} contains generic anatomy boilerplate",
            )
            self.assertFalse(
                any(rule.startswith("must be immediately recognizable as ") for rule in raw_rules),
                f"{page['page_id']} repeats a label instead of concrete identity geometry",
            )

            resolved = resolve_page_spec(page, ROOT)
            self.assertTrue(resolved.get("identity_rules"), page["page_id"])
            spec = load_monster_spec(page)
            self.assertTrue(
                set(spec["accuracy_checks"]).issubset(set(resolved["identity_rules"])),
                page["page_id"],
            )

    def test_every_page_preserves_canonical_scale_in_visual_hierarchy(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        for page in tome["pages"]:
            resolved = resolve_page_spec(page, ROOT)
            composition = resolved.get("composition", "").lower()
            self.assertIn("visually dominant focal subject", composition, page["page_id"])
            self.assertIn("canonical creature scale", composition, page["page_id"])
            self.assertIn("two to four large supporting forms", composition, page["page_id"])
            self.assertTrue(resolved.get("subject_scale_rule"), page["page_id"])
            self.assertNotIn("60–75% of page height", resolved.get("composition", ""), page["page_id"])
            self.assertNotIn("composition", page, page["page_id"])

    def test_every_page_has_nonempty_four_stage_review_contract(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        for page in tome["pages"]:
            self.assertEqual(review_stage_errors(page), [], page["page_id"])

    def test_every_page_has_explicit_physicality(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        for page in tome["pages"]:
            physicality = page.get("physicality") or {}
            self.assertTrue(physicality.get("mode"), page["page_id"])
            self.assertTrue(physicality.get("support"), page["page_id"])
            self.assertTrue(physicality.get("motion"), page["page_id"])

    def test_page_requirements_are_concrete(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        forbidden_placeholders = {"one clear story moment", "large open areas to color"}

        for page in tome["pages"]:
            requirements = {item.lower() for item in page["must_include"]}
            self.assertFalse(
                requirements.intersection(forbidden_placeholders),
                f"{page['page_id']} still has placeholder requirements",
            )
            self.assertGreaterEqual(len(requirements), 3, page["page_id"])


if __name__ == "__main__":
    unittest.main()
