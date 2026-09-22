import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from catalog_audit import audit_environment_variation_catalog, audit_monster_catalog
from manifest_validation import validate_manifest
from series_readiness import audit_series


class CatalogAndSeriesAuditTests(unittest.TestCase):
    def test_monster_catalog_has_no_repeated_family_without_profile(self):
        report = audit_monster_catalog(ROOT)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["pass"])
        self.assertGreaterEqual(report["family_profiles"], 10)

    def test_environment_variation_registry_covers_every_family(self):
        report = audit_environment_variation_catalog(ROOT)
        self.assertTrue(report["pass"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["environment_families"], 8)
        self.assertEqual(report["variation_families"], 8)

    def test_series_readiness_is_honest(self):
        report = audit_series(ROOT)
        self.assertEqual(report["environment_variation_families"], 8)
        self.assertTrue(report["pass"])
        self.assertEqual(report["books_registered"], 8)
        self.assertGreaterEqual(report["source_registry_entries"], 50)
        tome_i = next(row for row in report["books"] if row["book_id"] == "TOME-I")
        self.assertTrue(tome_i["production_ready"])
        future = [row for row in report["books"] if row["book_id"] != "TOME-I"]
        self.assertTrue(all(not row["production_ready"] for row in future))

    def test_environment_profile_overuse_fails_manifest(self):
        source = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        tome = {
            "tome_id": "TEST-DIVERSITY",
            "title": "Diversity Test",
            "theme": "test",
            "total_pages": 5,
            "pages": [],
        }
        base = deepcopy(source["pages"][0])
        for index in range(5):
            page = deepcopy(base)
            page["page_id"] = f"D-{index + 1:02d}"
            page["order"] = index + 1
            page["moment"] = f"distinct moment {index + 1}"
            page["environment_variant"] = {
                "landmark": f"distinct landmark {index + 1}",
                "framing": f"distinct framing {index + 1}",
                "interaction": f"distinct interaction {index + 1}",
            }
            tome["pages"].append(page)
        errors = validate_manifest(ROOT, tome, ROOT / "data" / "monsters")
        self.assertTrue(any("used 5 times" in error for error in errors))

    def test_tome_i_meets_environment_diversity_budget(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        errors = validate_manifest(ROOT, tome, ROOT / "data" / "monsters")
        self.assertFalse(any("maximum is" in error for error in errors))
        self.assertFalse(any("consecutive pages" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
