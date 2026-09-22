import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from catalog_audit import audit_environment_variation_catalog, audit_monster_catalog
from manifest_validation import validate_manifest
from monster_recipe_audit import audit_monster_recipes
from series_readiness import audit_series


class CatalogAndSeriesAuditTests(unittest.TestCase):
    def test_monster_catalog_has_no_repeated_family_without_profile(self):
        report = audit_monster_catalog(ROOT)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["pass"])
        self.assertTrue(report["recipe_policy_pass"])
        self.assertGreaterEqual(report["family_profiles"], 10)
        self.assertGreaterEqual(report["minimal_v3_plus"], 10)

    def test_v3_recipe_rejects_family_owned_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "config").mkdir(parents=True)
            (root / "data" / "monsters").mkdir(parents=True)
            (root / "data" / "monster_families").mkdir(parents=True)

            contract_text = (
                ROOT / "config" / "universal_monster_contract.json"
            ).read_text(encoding="utf-8")
            (root / "config" / "universal_monster_contract.json").write_text(
                contract_text,
                encoding="utf-8",
            )
            (root / "data" / "monster_families" / "kobold.json").write_text(
                "{}",
                encoding="utf-8",
            )

            bad_recipe = {
                "schema_version": 3,
                "monster_id": "bad-kobold",
                "monster_name": "Bad Kobold",
                "family_profile": "kobold",
                "visual_identity": {
                    "silhouette": "duplicated family anatomy"
                },
            }
            (root / "data" / "monsters" / "bad-kobold.json").write_text(
                json.dumps(bad_recipe),
                encoding="utf-8",
            )

            report = audit_monster_recipes(root)
            self.assertFalse(report["pass"])
            self.assertTrue(
                any(
                    "duplicates family-owned fields: visual_identity" in error
                    for error in report["errors"]
                )
            )

    def test_environment_variation_registry_covers_every_family(self):
        report = audit_environment_variation_catalog(ROOT)
        self.assertTrue(report["pass"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["environment_families"], 8)
        self.assertEqual(report["variation_families"], 8)

    def test_series_readiness_is_honest(self):
        report = audit_series(ROOT)
        self.assertEqual(report["environment_variation_families"], 8)
        self.assertEqual(report["environment_component_catalogs"], 8)
        self.assertGreaterEqual(report["environment_components"], 800)
        self.assertGreaterEqual(report["environment_overlays"], 8)
        self.assertTrue(report["pass"])
        self.assertEqual(report["books_registered"], 8)
        self.assertGreaterEqual(report["source_registry_entries"], 50)
        tome_i = next(
            row for row in report["books"] if row["book_id"] == "TOME-I"
        )
        self.assertTrue(tome_i["production_ready"])
        self.assertTrue(tome_i["calibration_required"])
        self.assertFalse(tome_i["calibration_complete"])
        self.assertFalse(tome_i["mass_generation_ready"])
        self.assertFalse(
            report["golden_five_calibration"]["production_calibrated"]
        )
        future = [
            row for row in report["books"] if row["book_id"] != "TOME-I"
        ]
        self.assertTrue(all(not row["production_ready"] for row in future))

    def test_environment_profile_overuse_fails_manifest(self):
        source = json.loads(
            (ROOT / "data" / "tome-I.json").read_text(encoding="utf-8")
        )
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
        tome = json.loads(
            (ROOT / "data" / "tome-I.json").read_text(encoding="utf-8")
        )
        errors = validate_manifest(ROOT, tome, ROOT / "data" / "monsters")
        self.assertFalse(any("maximum is" in error for error in errors))
        self.assertFalse(any("consecutive pages" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
