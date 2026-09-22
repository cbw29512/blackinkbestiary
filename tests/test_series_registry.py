import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from book_registry import load_series, series_status


class SeriesRegistryTests(unittest.TestCase):
    def test_eight_books_are_registered(self):
        series = load_series()
        self.assertEqual(len(series["books"]), 8)
        self.assertEqual(series["books"][0]["book_id"], "TOME-I")
        self.assertEqual(series["books"][0]["title"], "Caves & Dungeons")
        self.assertEqual(series["books"][-1]["book_id"], "TOME-VIII")

    def test_future_books_use_configured_page_counts_and_minimal_recipes(self):
        series = load_series()
        for book in series["books"][1:]:
            slug = book["book_id"].lower()
            path = ROOT / "data" / "book_plans" / f"{slug}.json"
            plan = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(plan["book_id"], book["book_id"])
            self.assertEqual(len(plan["slots"]), book["target_pages"])
            self.assertEqual(
                [slot["order"] for slot in plan["slots"]],
                list(range(1, book["target_pages"] + 1)),
            )
            self.assertEqual(plan["page_contract"], "black-ink-page-v1")
            for slot in plan["slots"]:
                self.assertEqual(slot["page_contract"], "black-ink-page-v1")
                self.assertNotIn("habitat", slot)
                self.assertNotIn("composition", slot)
                self.assertIn("environment_profile_id", slot)
                self.assertIn("environment_variant", slot)
                self.assertEqual(
                    set(slot["environment_variant"]),
                    {"landmark", "framing", "interaction"},
                )
                self.assertEqual(
                    set(slot["physicality"]),
                    {"mode", "support", "motion"},
                )

    def test_only_existing_production_files_are_reported_ready(self):
        rows = series_status(ROOT)
        self.assertEqual(len(rows), 8)
        tome_i = next(row for row in rows if row["book_id"] == "TOME-I")
        self.assertTrue(tome_i["production_files_complete"])
        for row in rows:
            if row["book_id"] != "TOME-I":
                self.assertTrue(row["plan_exists"])
                self.assertFalse(row["production_files_complete"])


if __name__ == "__main__":
    unittest.main()
