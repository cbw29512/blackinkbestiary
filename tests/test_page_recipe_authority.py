import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from edit_prompt import build_edit_prompt
from page_contract import load_page_contract, resolve_page_spec
from page_recipe_audit import audit_manifest_recipe_debt
from prompt_builder import build_prompt
from scene_relationships import active_relationship_rules


class PageRecipeAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        cls.i01 = next(page for page in tome["pages"] if page["page_id"] == "I-01")
        cls.i02 = next(page for page in tome["pages"] if page["page_id"] == "I-02")

    def test_contract_marks_legacy_fields_non_authoritative(self):
        contract = load_page_contract(ROOT / "config" / "universal_page_contract.json")
        authority = contract["generation_authority"]
        legacy = set(authority["legacy_non_authoritative_fields"])
        self.assertEqual(contract["contract_id"], "black-ink-page-v1")
        self.assertTrue(
            {"identity_rules", "must_include", "coloring_rules", "modify"}.issubset(legacy)
        )
        self.assertIn("review_notes", authority["review_correction_source"])


    def test_tome_i_is_safe_for_future_legacy_strip(self):
        report = audit_manifest_recipe_debt(ROOT, ROOT / "data" / "tome-I.json")
        self.assertTrue(report["safe_to_strip_legacy"])
        self.assertEqual(report["pages_missing_authoritative_fields"], [])
        self.assertGreater(report["pages_with_legacy_fields"], 0)
        self.assertGreater(report["legacy_field_counts"].get("must_include", 0), 0)

    def test_resolver_uses_canonical_identity_and_coloring_defaults(self):
        page = deepcopy(self.i01)
        page["identity_rules"] = ["LEGACY IDENTITY POISON"]
        page["coloring_rules"] = {"color": "purple", "detail_density": "extreme"}

        resolved = resolve_page_spec(page, ROOT)

        self.assertNotIn("LEGACY IDENTITY POISON", resolved["identity_rules"])
        self.assertEqual(resolved["coloring_rules"]["color"], "black_on_white")
        self.assertEqual(resolved["coloring_rules"]["detail_density"], "medium_low")

    def test_generation_prompt_ignores_legacy_positive_instructions(self):
        page = deepcopy(self.i01)
        page["identity_rules"] = ["LEGACY IDENTITY POISON"]
        page["must_include"] = ["LEGACY PROP POISON"]
        page["modify"] = {
            "preserve": ["LEGACY PRESERVE POISON"],
            "change": ["LEGACY CHANGE POISON"],
            "avoid": ["LEGACY MODIFY AVOID POISON"],
        }

        text = build_prompt(page)

        self.assertNotIn("LEGACY IDENTITY POISON", text)
        self.assertNotIn("LEGACY PROP POISON", text)
        self.assertNotIn("LEGACY PRESERVE POISON", text)
        self.assertNotIn("LEGACY CHANGE POISON", text)
        self.assertIn("PAGE RECIPE LOCK", text)
        self.assertIn(page["environment_variant"]["framing"], text)

    def test_edit_prompt_uses_review_state_not_manifest_modify(self):
        page = deepcopy(self.i01)
        page["modify"] = {
            "preserve": ["LEGACY PRESERVE POISON"],
            "change": ["LEGACY CHANGE POISON"],
            "avoid": ["LEGACY MODIFY AVOID POISON"],
        }

        text = build_edit_prompt(
            page,
            {
                "text": "CURRENT REVIEW CORRECTION",
                "quick_tags": ["more white space"],
                "preserve_dimensions": ["monster_identity"],
            },
        )

        self.assertIn("CURRENT REVIEW CORRECTION", text)
        self.assertIn("more white space", text)
        self.assertNotIn("LEGACY PRESERVE POISON", text)
        self.assertNotIn("LEGACY CHANGE POISON", text)

    def test_relationship_rules_ignore_legacy_must_include(self):
        page = deepcopy(self.i02)
        page["must_include"] = ["tripwire"]
        page["moment"] = "raising a copper coin as an offering"
        rules = active_relationship_rules(page, ROOT)
        rule_ids = {rule["rule_id"] for rule in rules}

        self.assertIn("offering_to_shrine", rule_ids)
        self.assertNotIn("tripwire_trigger", rule_ids)


if __name__ == "__main__":
    unittest.main()
