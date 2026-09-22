import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from monster_catalog import resolve_monster_spec
from prompt_builder import build_prompt


class CreatureCatalogTests(unittest.TestCase):
    def test_goblin_variant_inherits_family_failures(self):
        spec = resolve_monster_spec("goblin-minion")
        avoid = " ".join(spec["visual_identity"]["must_avoid"]).lower()
        failure_ids = {item["id"] for item in spec.get("known_failure_modes", [])}
        self.assertIn("cute elf-child face", avoid)
        self.assertIn("imp or devil face", avoid)
        self.assertIn("furry or fluffy silhouette", avoid)
        self.assertIn("imp_drift", failure_ids)
        self.assertEqual(spec["catalog"]["family_profile"], "data/monster_families/goblin.json")

    def test_bugbear_family_blocks_sasquatch_drift(self):
        spec = resolve_monster_spec("bugbear-warrior")
        avoid = " ".join(spec["visual_identity"]["must_avoid"]).lower()
        failure_ids = {item["id"] for item in spec.get("known_failure_modes", [])}
        self.assertIn("sasquatch or bigfoot silhouette", avoid)
        self.assertIn("ape face", avoid)
        self.assertIn("sasquatch_drift", failure_ids)

    def test_hobgoblin_family_blocks_orc_and_goblin_drift(self):
        spec = resolve_monster_spec("hobgoblin-warrior")
        avoid = " ".join(spec["visual_identity"]["must_avoid"]).lower()
        failures = {item["id"] for item in spec.get("known_failure_modes", [])}
        self.assertIn("orc tusks", avoid)
        self.assertIn("tiny goblin body", avoid)
        self.assertIn("orc_drift", failures)
        self.assertIn("goblin_drift", failures)
        self.assertEqual(spec["family_profile"], "hobgoblin")

    def test_minimal_bugbear_recipe_inherits_complete_family_identity(self):
        raw = json.loads((ROOT / "data" / "monsters" / "bugbear-stalker.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["schema_version"], 3)
        self.assertNotIn("visual_identity", raw)
        self.assertNotIn("accuracy_checks", raw)
        self.assertNotIn("size", raw)
        self.assertNotIn("creature_type", raw)

        spec = resolve_monster_spec("bugbear-stalker")
        self.assertEqual(spec["monster_contract"], "black-ink-monster-v3")
        self.assertTrue(spec["catalog"]["minimal_recipe"])
        self.assertEqual(spec["family"], "bugbear")
        self.assertEqual(spec["size"], "medium")
        self.assertEqual(spec["creature_type"], "goblinoid humanoid")
        self.assertIn("ape face or primate muzzle", spec["visual_identity"]["must_avoid"])
        self.assertIn("ape_drift", {item["id"] for item in spec["known_failure_modes"]})

    def test_family_failure_modes_drive_bugbear_prompt(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-09")
        text = build_prompt(page)
        self.assertIn("KNOWN IDENTITY DRIFT TO PREVENT", text)
        self.assertIn("gorilla, ape-man, or primate", text)
        self.assertIn("CORRECTION:", text)

    def test_entire_monster_catalog_is_minimal_v3(self):
        from catalog_audit import audit_monster_catalog

        report = audit_monster_catalog(ROOT)
        self.assertEqual(report["monster_specs"], 50)
        self.assertEqual(report["minimal_recipe_specs"], 50)
        self.assertGreaterEqual(report["family_profiles"], 30)
        self.assertGreaterEqual(report["variant_profiles"], 19)
        self.assertGreaterEqual(report["variant_backed_specs"], 19)
        self.assertEqual(report["errors"], [])

    def test_variant_profile_preserves_specialized_identity(self):
        cube = resolve_monster_spec("gelatinous-cube")
        armor = resolve_monster_spec("animated-armor")
        zombie = resolve_monster_spec("ogre-zombie")

        self.assertEqual(cube["catalog"]["variant_profile"], "data/monster_variants/gelatinous-cube.json")
        self.assertIn("clear cube geometry", cube["visual_identity"]["must_keep"])
        self.assertIn("no visible body inside", armor["visual_identity"]["must_keep"])
        self.assertIn("obvious undead posture", zombie["visual_identity"]["must_keep"])

    def test_variant_family_mismatch_is_rejected(self):
        raw = json.loads(
            (ROOT / "data" / "monsters" / "gelatinous-cube.json").read_text(encoding="utf-8")
        )
        self.assertEqual(raw["family_profile"], "ooze")
        self.assertEqual(raw["variant_profile"], "gelatinous-cube")

    def test_all_family_profiles_pass_expanded_dna_audit(self):
        from catalog_audit import audit_monster_catalog

        report = audit_monster_catalog(ROOT)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["pass"])

    def test_family_scene_dna_is_injected_into_prompt(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-09")
        text = build_prompt(page)
        self.assertIn("CANONICAL LIMBS / EXTREMITIES", text)
        self.assertIn("CANONICAL SIZE IMPRESSION", text)
        self.assertIn("CANONICAL NATURAL POSTURE", text)
        self.assertIn("CANONICAL BEHAVIOR STYLE", text)
        self.assertNotIn("CANONICAL ENVIRONMENT FIT", text)
        self.assertIn("PAGE ENVIRONMENT AUTHORITY", text)

    def test_kobold_family_identity_merges_with_variant(self):
        spec = resolve_monster_spec("kobold-warrior")
        keep = spec["visual_identity"]["must_keep"]
        self.assertIn("long reptilian snout", keep)
        self.assertIn("visible tail", keep)
        self.assertEqual(spec["family_profile"], "kobold")
        self.assertEqual(spec["schema_version"], 3)


if __name__ == "__main__":
    unittest.main()
