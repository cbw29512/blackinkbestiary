import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))
sys.path.insert(0, str(ROOT / "scripts"))

from calibration_service import public_calibration_state
from edit_prompt import build_edit_prompt
from page_contract import load_page_contract, resolve_page_spec
from page_recipe_audit import audit_manifest_recipe_debt
from prompt_builder import build_prompt
from scene_relationships import active_relationship_rules
from smoke_test_support import load_current


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
        self.assertEqual(authority["runtime_compatibility_retained"], [])
        self.assertIn("review_notes", authority["review_correction_source"])

    def test_tome_i_legacy_recipe_migration_is_complete(self):
        report = audit_manifest_recipe_debt(ROOT, ROOT / "data" / "tome-I.json")
        self.assertTrue(report["safe_to_strip_generation_legacy"])
        self.assertTrue(report["migration_complete"])
        self.assertEqual(report["pages_missing_authoritative_fields"], [])
        self.assertEqual(report["pages_with_legacy_fields"], 0)
        self.assertTrue(all(count == 0 for count in report["legacy_field_counts"].values()))

    def test_raw_tome_pages_are_minimal(self):
        for page in (self.i01, self.i02):
            self.assertNotIn("monster_name", page)
            self.assertNotIn("habitat", page)
            self.assertNotIn("identity_rules", page)
            self.assertNotIn("must_include", page)
            self.assertNotIn("coloring_rules", page)
            self.assertNotIn("reference_image", page)
            self.assertNotIn("modify", page)

    def test_resolver_uses_canonical_identity_and_coloring_defaults(self):
        page = deepcopy(self.i01)
        page["identity_rules"] = ["LEGACY IDENTITY POISON"]
        page["coloring_rules"] = {"color": "purple", "detail_density": "extreme"}
        resolved = resolve_page_spec(page, ROOT)
        self.assertEqual(resolved["monster_name"], "Kobold Warrior")
        self.assertEqual(resolved["habitat"], "Trapped Stone Corridor")
        self.assertNotIn("LEGACY IDENTITY POISON", resolved["identity_rules"])
        self.assertEqual(resolved["coloring_rules"]["color"], "black_on_white")
        self.assertEqual(resolved["coloring_rules"]["detail_density"], "medium_low")


    def test_removed_page_avoids_still_resolve_from_correct_owners(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        pages = {page["page_id"]: page for page in tome["pages"]}

        pantry = resolve_page_spec(pages["I-03"], ROOT)["must_avoid"]
        self.assertIn("cute elf-child face", pantry)
        self.assertIn("imp or devil face", pantry)
        self.assertIn("modern cabinets", pantry)
        self.assertIn("appliances", pantry)

        hobgoblin = resolve_page_spec(pages["I-06"], ROOT)["must_avoid"]
        self.assertIn("orc tusks", hobgoblin)
        self.assertIn("boar-like nose", hobgoblin)
        self.assertIn("oversized goblin ears", hobgoblin)

        bugbear = resolve_page_spec(pages["I-08"], ROOT)["must_avoid"]
        self.assertIn("floating or unsupported pose", bugbear)
        self.assertIn(
            "non-flying creature shown jumping, falling, dropping, or frozen in midair",
            bugbear,
        )

        crawlway = resolve_page_spec(pages["I-09"], ROOT)["must_avoid"]
        self.assertIn("normal-height corridor", crawlway)
        self.assertIn("smooth featureless hallway walls", crawlway)
        self.assertIn("modern drywall or office hallway", crawlway)

    def test_generation_prompt_ignores_legacy_positive_instructions(self):
        page = deepcopy(self.i01)
        page["identity_rules"] = ["LEGACY IDENTITY POISON"]
        page["must_include"] = ["LEGACY PROP POISON"]
        page["modify"] = {
            "preserve": ["LEGACY PRESERVE POISON"],
            "change": ["LEGACY CHANGE POISON"],
        }
        text = build_prompt(page)
        self.assertNotIn("LEGACY IDENTITY POISON", text)
        self.assertNotIn("LEGACY PROP POISON", text)
        self.assertNotIn("LEGACY PRESERVE POISON", text)
        self.assertIn("PAGE RECIPE LOCK", text)
        self.assertIn(page["environment_variant"]["framing"], text)

    def test_edit_prompt_uses_review_state_not_manifest_modify(self):
        page = deepcopy(self.i01)
        page["modify"] = {"change": ["LEGACY CHANGE POISON"]}
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
        self.assertNotIn("LEGACY CHANGE POISON", text)

    def test_relationship_rules_ignore_legacy_must_include(self):
        page = deepcopy(self.i02)
        page["must_include"] = ["tripwire"]
        page["moment"] = "raising a copper coin as an offering"
        rule_ids = {
            rule["rule_id"] for rule in active_relationship_rules(page, ROOT)
        }
        self.assertIn("offering_to_shrine", rule_ids)
        self.assertNotIn("tripwire_trigger", rule_ids)

    def test_raw_manifest_consumers_resolve_display_fields(self):
        smoke_page, _ = load_current(ROOT)
        self.assertEqual(smoke_page["monster_name"], "Kobold Warrior")
        self.assertEqual(smoke_page["habitat"], "Trapped Stone Corridor")

        calibration = public_calibration_state(ROOT)
        i01 = next(row for row in calibration["pages"] if row["page_id"] == "I-01")
        self.assertEqual(i01["monster_name"], "Kobold Warrior")
        self.assertEqual(i01["habitat"], "Trapped Stone Corridor")


if __name__ == "__main__":
    unittest.main()
