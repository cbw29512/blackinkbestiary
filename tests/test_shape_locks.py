import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from prompt_builder import build_prompt, build_supervisor_checklist
from monster_catalog import resolve_monster_spec


class ShapeLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        cls.pages = {page["page_id"]: page for page in tome["pages"]}

    def test_prompt_reserves_blank_outer_print_margin(self):
        text = build_prompt(self.pages["I-01"])
        self.assertIn("outer eight percent of the page", text)
        self.assertIn("completely blank white print margin", text)
        self.assertIn("no creature anatomy", text)

    def test_kobold_shape_lock_proves_miniature_scale(self):
        text = build_prompt(self.pages["I-01"])
        self.assertIn("SHAPE-FIRST RENDER LOCK", text)
        self.assertIn("normal doorway/corridor opening", text)
        self.assertIn("one-third to one-half", text)

    def test_darkmantle_shape_lock_forbids_humanoid_topology(self):
        text = build_prompt(self.pages["I-14"])
        self.assertIn("one continuous ceiling-clinging cloak/cap body", text)
        self.assertIn("no separate head silhouette, torso", text.lower())
        self.assertIn("NON-FLIGHT POSE LOCK", text)
        self.assertIn("not airborne", text)

    def test_bat_and_centipede_shape_locks_are_literal(self):
        bat = build_prompt(self.pages["I-16"])
        centipede = build_prompt(self.pages["I-20"])
        self.assertIn("exactly four limbs total", bat)
        self.assertIn("two forelimbs that ARE the membrane wings", bat)
        self.assertIn("every visible trunk segment carries exactly one pair", centipede)

    def test_small_humanoid_prompt_uses_literal_architecture_ratio(self):
        text = build_prompt(self.pages["I-01"])
        self.assertIn("SMALL-HUMANOID SCALE EVIDENCE", text)
        self.assertIn("one-third to one-half", text)
        self.assertIn("normal doorway/corridor opening", text)

    def test_supported_darkmantle_prompt_suppresses_flight_cues(self):
        text = build_prompt(self.pages["I-14"])
        self.assertIn("NON-FLIGHT POSE LOCK", text)
        self.assertIn("not airborne", text)
        self.assertIn("one continuous ceiling-clinging cloak/cap body", text)
        self.assertNotIn("controlled natural flight, but flight capability", text)

    def test_spiral_stair_uses_dedicated_helical_envelope(self):
        text = build_prompt(self.pages["I-10"])
        self.assertIn("SPACE ENVELOPE: spiral_stair", text)
        self.assertIn("wedge-shaped steps visibly curving around the center", text)
        self.assertIn("central newel, column, or open shaft", text)
        self.assertIn("straight staircase", text)

    def test_kicking_scene_requires_visible_impact_contact(self):
        text = build_prompt(self.pages["I-04"])
        self.assertIn("KICKING CONTACT LOCK", text)
        self.assertIn("striking foot visibly contacts the target", text)
        self.assertIn("KICKED LANTERN LOCK", text)
        self.assertIn("lantern tips, skids, or tumbles", text)

    def test_every_monster_family_has_required_positive_shape_lock(self):
        contract = json.loads(
            (ROOT / "config" / "universal_monster_contract.json").read_text(encoding="utf-8")
        )
        self.assertIn("visual_identity.shape_lock", contract["family_profile_required"])

        missing = []
        for path in sorted((ROOT / "data" / "monster_families").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            shape_lock = str((payload.get("visual_identity") or {}).get("shape_lock") or "").strip()
            if not shape_lock:
                missing.append(path.name)
        self.assertEqual(missing, [])

    def test_every_tome_i_monster_resolves_complete_positive_anatomy_contract(self):
        missing = []
        for path in sorted((ROOT / "data" / "monsters").glob("*.json")):
            spec_id = path.stem
            resolved = resolve_monster_spec(spec_id)
            visual = resolved.get("visual_identity") or {}
            absent = [
                key
                for key in ("shape_lock", "limb_structure", "silhouette", "body_shape")
                if not str(visual.get(key) or "").strip()
            ]
            if absent:
                missing.append((spec_id, absent))
        self.assertEqual(missing, [])

    def test_shape_lock_is_an_identity_review_gate(self):
        checks = build_supervisor_checklist(self.pages["I-14"])
        self.assertTrue(any(item.startswith("Shape-first body geometry reads as:") for item in checks))


if __name__ == "__main__":
    unittest.main()
