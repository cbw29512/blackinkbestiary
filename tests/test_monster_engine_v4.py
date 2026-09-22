import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from monster_brief import build_monster_brief
from monster_catalog import resolve_monster_spec
from monster_engine_audit import audit_monster_engine
from prompt_builder import build_prompt


class MonsterEngineV4Tests(unittest.TestCase):
    def test_v4_recipes_are_tiny_identity_pointers(self):
        for monster_id in ("animated-armor", "flying-sword", "gelatinous-cube"):
            raw = json.loads(
                (ROOT / "data" / "monsters" / f"{monster_id}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(raw["schema_version"], 4)
            self.assertEqual(raw["identity_profile"], monster_id)
            self.assertNotIn("visual_identity", raw)
            self.assertNotIn("accuracy_checks", raw)
            self.assertLess(len(json.dumps(raw)), 300)

    def test_species_profile_inherits_broad_family(self):
        armor = resolve_monster_spec("animated-armor")
        self.assertEqual(armor["family"], "construct")
        self.assertEqual(armor["size"], "medium")
        self.assertIn("robot_drift", {item["id"] for item in armor["known_failure_modes"]})
        self.assertIn("wearer_drift", {item["id"] for item in armor["known_failure_modes"]})
        self.assertEqual(armor["anatomy"]["limb_count"], 4)

    def test_object_and_ooze_render_modes_are_structured(self):
        sword = resolve_monster_spec("flying-sword")
        cube = resolve_monster_spec("gelatinous-cube")
        self.assertEqual(sword["render_identity"]["subject_mode"], "object")
        self.assertTrue(sword["locomotion"]["can_fly"])
        self.assertEqual(sword["anatomy"]["limb_count"], 0)
        self.assertEqual(cube["render_identity"]["subject_mode"], "amorphous")
        self.assertEqual(cube["anatomy"]["body_plan"], "rectilinear cubic ooze")

    def test_species_identity_no_longer_owns_page_only_props(self):
        sword = resolve_monster_spec("flying-sword")
        cube = resolve_monster_spec("gelatinous-cube")
        sword_text = json.dumps(sword["visual_identity"]).lower()
        cube_text = json.dumps(cube["visual_identity"]).lower()
        self.assertNotIn("pillar", sword_text)
        self.assertNotIn("suspended key", cube_text)
        self.assertNotIn("suspended bones", cube_text)

    def test_page_recipe_can_still_add_cube_story_debris(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-24")
        text = build_prompt(page)
        self.assertIn("MONSTER BRIEF — AUTHORITATIVE", text)
        self.assertIn("bones", text.lower())
        self.assertIn("key", text.lower())

    def test_monster_prompt_is_compact_not_legacy_prose_stack(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-09")
        text = build_prompt(page)
        self.assertEqual(text.count("MONSTER BRIEF — AUTHORITATIVE"), 1)
        self.assertNotIn("CANONICAL CORE IDENTITY", text)
        self.assertNotIn("CANONICAL SILHOUETTE", text)
        self.assertNotIn("CANONICAL HEAD", text)
        self.assertIn("MONSTER IDENTITY ANCHORS", text)
        self.assertIn("MONSTER DRIFT CORRECTIONS", text)

    def test_every_current_monster_brief_stays_under_budget(self):
        for path in sorted((ROOT / "data" / "monsters").glob("*.json")):
            spec = resolve_monster_spec(path.stem)
            brief = build_monster_brief(spec, ROOT)
            self.assertLessEqual(len(brief["brief"].split()), 105, path.stem)

    def test_audit_reports_migration_debt_without_hiding_it(self):
        report = audit_monster_engine(ROOT)
        self.assertTrue(report["pass"])
        self.assertGreaterEqual(report["v4_minimal_recipes"], 3)
        self.assertGreater(report["full_identity_recipes"], 0)
        self.assertFalse(report["migration_complete"])
        self.assertFalse(report["production_identity_ready"])


if __name__ == "__main__":
    unittest.main()
