import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from source_scope import monster_allowed


class ProductNorthStarTests(unittest.TestCase):
    def test_series_is_eight_environment_led_books(self):
        series = json.loads((ROOT / "data" / "series.json").read_text(encoding="utf-8"))
        self.assertEqual(len(series["books"]), 8)
        self.assertEqual(series["product_scope"]["ruleset"], "2024 SRD")
        self.assertEqual(series["product_scope"]["organization"], "hybrid_environment_led")
        self.assertTrue(all(book["target_pages"] == 50 for book in series["books"]))

    def test_all_books_inherit_same_engines_and_print_scope(self):
        series = json.loads((ROOT / "data" / "series.json").read_text(encoding="utf-8"))
        for book in series["books"]:
            self.assertEqual(book["page_contract"], "config/universal_page_contract.json")
            self.assertEqual(book["monster_contract"], "config/universal_monster_contract.json")
            self.assertEqual(book["kdp_print_standard"], "config/kdp_print_standard.json")
            self.assertEqual(book["content_scope"], "config/content_scope.json")

    def test_kdp_standard_is_85x11_300dpi_non_bleed(self):
        standard = json.loads((ROOT / "config" / "kdp_print_standard.json").read_text(encoding="utf-8"))
        self.assertEqual(standard["trim"]["width_inches"], 8.5)
        self.assertEqual(standard["trim"]["height_inches"], 11.0)
        self.assertFalse(standard["trim"]["bleed"])
        self.assertEqual(standard["raster_export"]["dpi"], 300)
        self.assertEqual(standard["raster_export"]["width_px"], 2550)
        self.assertEqual(standard["raster_export"]["height_px"], 3300)
        self.assertEqual(standard["page_content"]["dominant_subjects"], 1)

    def test_page_contract_requires_all_approval_pillars(self):
        contract = json.loads((ROOT / "config" / "universal_page_contract.json").read_text(encoding="utf-8"))
        gate = contract["approval_gate"]
        self.assertEqual(
            gate["thumbnail_pillars"],
            ["monster_identity", "environment_identity", "story_moment"],
        )
        self.assertTrue(gate["colorability"])
        self.assertTrue(gate["line_art_purity"])
        self.assertTrue(gate["environment_uniqueness"])
        self.assertTrue(gate["print_layout"])

    def test_tome_i_monsters_are_on_project_source_roster(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        for page in tome["pages"]:
            self.assertTrue(monster_allowed(page["monster_spec_id"], ROOT), page["page_id"])

    def test_all_books_inherit_story_engine(self):
        series = json.loads((ROOT / "data" / "series.json").read_text(encoding="utf-8"))
        self.assertEqual(series["story_contract"], "config/universal_story_contract.json")
        for book in series["books"]:
            self.assertEqual(book["story_contract"], "config/universal_story_contract.json")

    def test_engine_tracker_exists_and_names_current_priorities(self):
        tracker = (ROOT / "docs" / "ENGINE_V2_TRACKER.md").read_text(encoding="utf-8")
        self.assertIn("story-moment engine", tracker)
        self.assertIn("family DNA audit", tracker)
        self.assertIn("environment variation depth", tracker)
        self.assertIn("Golden Five", tracker)

    def test_environment_v3_is_built_for_hundreds_of_monsters(self):
        environment = json.loads(
            (ROOT / "config" / "universal_environment_contract.json").read_text(encoding="utf-8")
        )
        monster = json.loads(
            (ROOT / "config" / "universal_monster_contract.json").read_text(encoding="utf-8")
        )
        self.assertEqual(environment["contract_id"], "black-ink-environment-v3")
        self.assertIn("component_engine", environment)
        self.assertIn("overlay_engine", environment)
        self.assertEqual(len(environment["component_engine"]["required_groups"]), 12)
        self.assertIn("Hundreds of monster recipes remain small", monster["scalability_rule"])
        self.assertIn("environment engine", monster["environment_ownership"]["rule"].lower())

    def test_colorability_outranks_story_complexity(self):
        page = json.loads((ROOT / "config" / "universal_page_contract.json").read_text(encoding="utf-8"))
        coloring = json.loads((ROOT / "config" / "coloring_page_standard.json").read_text(encoding="utf-8"))
        story = json.loads((ROOT / "config" / "universal_story_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(page["production_priority"][0], "colorability")
        self.assertEqual(coloring["priority_order"][0], "fun and satisfying to color")
        self.assertIn("colorability wins", story["priority_rule"].lower())
        self.assertEqual(story["story_budget"]["primary_beats"], 1)
        self.assertEqual(story["story_budget"]["environment_interactions"], [1, 1])


if __name__ == "__main__":
    unittest.main()
