import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from book_promotion import build_manifest_from_plan
from book_scaffold import build_book_plan, build_book_record
from manifest_validation import validate_manifest
from page_contract import resolve_page_spec
from prompt_builder import build_prompt


class UniversalPageContractTests(unittest.TestCase):
    def minimal_page(self):
        return {
            "page_id": "IX-01",
            "order": 1,
            "monster_spec_id": "kobold-warrior",
            "moment": "testing a pressure plate before an intruder arrives",
            "archetype": "trap_scene",
            "environment_profile_id": "underground.trapped-stone-corridor",
            "environment_variant": {
                "landmark": "large pressure plate beside a wall torch",
                "framing": "low corridor perspective",
                "interaction": "kobold tests the pressure plate while watching the pit mechanism",
            },
            "physicality": {
                "mode": "grounded",
                "support": "both feet visibly contact the flagstone floor",
                "motion": "crouched testing posture with weight balanced over the feet",
            },
        }

    def test_minimal_recipe_resolves_derived_fields(self):
        raw = self.minimal_page()
        self.assertNotIn("monster_name", raw)
        self.assertNotIn("habitat", raw)
        self.assertNotIn("composition", raw)
        self.assertNotIn("must_avoid", raw)

        page = resolve_page_spec(raw, ROOT)
        self.assertEqual(page["monster_name"], "Kobold Warrior")
        self.assertEqual(page["habitat"], "Trapped Stone Corridor")
        self.assertIn("60–75% of page height", page["composition"])
        self.assertTrue(page["must_avoid"])
        self.assertEqual(page["_resolved"]["contract_id"], "black-ink-page-v2")

    def test_canonical_catalog_names_override_stale_page_display_fields(self):
        raw = self.minimal_page()
        raw["monster_name"] = "Wrong Creature Name"
        raw["habitat"] = "Generic Hallway"
        tome = {
            "tome_id": "TEST-LEGACY",
            "title": "Legacy Field Test",
            "theme": "test",
            "total_pages": 1,
            "pages": [raw],
        }
        errors = validate_manifest(ROOT, tome, ROOT / "data" / "monsters")
        self.assertTrue(any("legacy derived fields" in error for error in errors))

    def test_minimal_recipe_generates_complete_prompt(self):
        text = build_prompt(self.minimal_page())
        self.assertIn("SUBJECT: Kobold Warrior", text)
        self.assertIn("HABITAT: Trapped Stone Corridor", text)
        self.assertIn("60–75% of page height", text)
        self.assertIn("PHYSICAL SUPPORT / CONTACT", text)
        self.assertIn("GLOBAL ENVIRONMENT STANDARD", text)

    def test_minimal_manifest_passes_validation(self):
        tome = {
            "tome_id": "TOME-IX",
            "title": "Test Tome",
            "theme": "test",
            "total_pages": 1,
            "pages": [self.minimal_page()],
        }
        errors = validate_manifest(ROOT, tome, ROOT / "data" / "monsters")
        self.assertEqual(errors, [])

    def test_book_scaffold_supports_non_fifty_page_books(self):
        book = build_book_record(
            "HOLIDAY-I",
            "Holiday Monsters",
            "Seasonal fantasy creatures",
            24,
            ["winter village", "haunted harvest", "festive dungeon"],
        )
        plan = build_book_plan(book, "H")
        self.assertEqual(book["target_pages"], 24)
        self.assertEqual(len(plan["slots"]), 24)
        self.assertNotIn("habitat", plan["slots"][0])
        self.assertNotIn("composition", plan["slots"][0])
        self.assertEqual(book["kdp_print_standard"], "config/kdp_print_standard.json")
        self.assertEqual(book["content_scope"], "config/content_scope.json")
        self.assertEqual(book["environment_contract"], "config/universal_environment_contract.json")
        self.assertEqual(plan["page_contract"], "black-ink-page-v2")
        self.assertEqual(plan["monster_contract"], "black-ink-monster-v3")
        self.assertEqual(plan["environment_contract"], "black-ink-environment-v3")
        self.assertEqual(plan["story_contract"], "black-ink-story-v2")
        self.assertEqual(plan["print_standard"], "black-ink-kdp-8.5x11-v1")
        self.assertEqual(plan["source_scope"], "2024 SRD")

    def test_completed_plan_promotes_to_minimal_manifest(self):
        book = build_book_record("TOME-IX", "Test Tome", "test", 1, ["dungeon"])
        plan = build_book_plan(book, "IX")
        plan["slots"][0].update(self.minimal_page())
        plan["slots"][0]["planning_status"] = "ready"
        manifest, errors = build_manifest_from_plan(plan, ROOT)
        self.assertEqual(errors, [])
        self.assertEqual(manifest["total_pages"], 1)
        self.assertNotIn("habitat", manifest["pages"][0])
        self.assertEqual(
            validate_manifest(ROOT, manifest, ROOT / "data" / "monsters"),
            [],
        )

    def test_nonflyer_cannot_use_powered_flight(self):
        page = self.minimal_page()
        page["physicality"] = {
            "mode": "flying",
            "support": "unsupported in open air",
            "motion": "hovering",
        }
        tome = {
            "tome_id": "TEST-FLIGHT",
            "title": "Flight Test",
            "theme": "test",
            "total_pages": 1,
            "pages": [page],
        }
        errors = validate_manifest(ROOT, tome, ROOT / "data" / "monsters")
        self.assertTrue(any("non-flying creature" in error for error in errors))

    def test_flying_family_can_use_powered_flight(self):
        page = self.minimal_page()
        page["monster_spec_id"] = "giant-bat"
        page["physicality"] = {
            "mode": "flying",
            "support": "airborne by wing-powered flight",
            "motion": "banking through the cavern",
        }
        resolved = resolve_page_spec(page, ROOT)
        self.assertTrue(resolved["locomotion"]["can_fly"])

    def test_unstable_jump_or_fall_pose_is_rejected(self):
        page = self.minimal_page()
        page["physicality"] = {
            "mode": "falling",
            "support": "no support",
            "motion": "dropping downward",
        }
        tome = {
            "tome_id": "TEST-FALL",
            "title": "Fall Test",
            "theme": "test",
            "total_pages": 1,
            "pages": [page],
        }
        errors = validate_manifest(ROOT, tome, ROOT / "data" / "monsters")
        self.assertTrue(any("unstable coloring pose" in error for error in errors))

    def test_i08_is_now_stably_grounded(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-08")
        resolved = resolve_page_spec(page, ROOT)
        self.assertFalse(resolved["locomotion"]["can_fly"])
        self.assertEqual(resolved["physicality"]["mode"], "grounded")
        self.assertIn("both feet", resolved["physicality"]["support"])

    def test_all_registered_books_share_universal_contracts(self):
        series = json.loads((ROOT / "data" / "series.json").read_text(encoding="utf-8"))
        self.assertEqual(series["page_contract"], "config/universal_page_contract.json")
        self.assertEqual(series["monster_contract"], "config/universal_monster_contract.json")
        self.assertEqual(series["environment_contract"], "config/universal_environment_contract.json")
        self.assertEqual(series["print_standard"], "config/kdp_print_standard.json")
        self.assertTrue(all(
            book["page_contract"] == "config/universal_page_contract.json"
            and book["monster_contract"] == "config/universal_monster_contract.json"
            and book["environment_contract"] == "config/universal_environment_contract.json"
            for book in series["books"]
        ))


if __name__ == "__main__":
    unittest.main()
