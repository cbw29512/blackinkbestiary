import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from equipment_attachments import attachment_assignments
from equipment_policy import canonical_weapon_gear, load_equipment_rules
from monster_catalog import resolve_monster_spec


class EquipmentCatalogPolicyTests(unittest.TestCase):

    def test_hobgoblin_shield_gets_hand_or_forearm_attachment(self):
        spec = resolve_monster_spec("hobgoblin-warrior")
        assignments = attachment_assignments(spec, ROOT)
        shield = next(item for item in assignments if item["item"] == "medium shield")
        self.assertEqual(shield["group_id"], "shield")
        self.assertIn("forearm", " ".join(shield["directives"]))

    def test_drider_quiver_gets_body_attachment(self):
        spec = resolve_monster_spec("drider")
        assignments = attachment_assignments(spec, ROOT)
        quiver = next(item for item in assignments if item["item"] == "quiver")
        self.assertEqual(quiver["group_id"], "quiver")
        self.assertIn("back", " ".join(quiver["directives"]))

    def test_kobold_armor_and_straps_get_torso_attachment(self):
        spec = resolve_monster_spec("kobold-warrior")
        assignments = {item["item"]: item["group_id"] for item in attachment_assignments(spec, ROOT)}
        self.assertEqual(assignments["rough leather straps"], "torso_gear")
        self.assertEqual(assignments["light scavenged armor"], "torso_gear")

    def test_ogre_belt_gets_waist_attachment(self):
        spec = resolve_monster_spec("ogre")
        assignments = {item["item"]: item["group_id"] for item in attachment_assignments(spec, ROOT)}
        self.assertEqual(assignments["thick belt"], "waist_gear")

    def test_zombie_restraints_get_real_attachment_points(self):
        spec = resolve_monster_spec("ogre-zombie")
        assignments = {item["item"]: item["group_id"] for item in attachment_assignments(spec, ROOT)}
        self.assertEqual(assignments["dragging chains"], "restraints")
        self.assertEqual(assignments["broken shackles"], "restraints")

    def test_specific_attachment_rules_beat_generic_wrap_rules(self):
        goblin = resolve_monster_spec("goblin-warrior")
        assignments = {
            item["item"]: item["group_id"]
            for item in attachment_assignments(goblin, ROOT)
        }
        self.assertEqual(assignments["simple foot wraps"], "foot_gear")

    def test_robe_fasteners_use_accessory_attachment(self):
        lich = resolve_monster_spec("lich")
        assignments = {
            item["item"]: item["group_id"]
            for item in attachment_assignments(lich, ROOT)
        }
        self.assertEqual(assignments["few simple robe fasteners"], "worn_accessory")

    def test_all_monster_signature_gear_is_concrete_and_unambiguous(self):
        payload = load_equipment_rules(ROOT / "config" / "creature_equipment_rules.json")
        forbidden = (
            " or ",
            "if scene allows",
            "if unobtrusive",
            "if any",
            "oversized",
        )
        armed = 0
        for path in sorted((ROOT / "data" / "monsters").glob("*.json")):
            spec = resolve_monster_spec(path.stem)
            gear = (spec.get("visual_identity") or {}).get("signature_gear") or []
            weapons = canonical_weapon_gear(spec, payload)
            if weapons:
                armed += 1
            for item in gear:
                lower = str(item).lower()
                self.assertFalse(
                    any(term in lower for term in forbidden),
                    f"{path.stem}: ambiguous signature gear {item!r}",
                )
        self.assertGreaterEqual(armed, 10)


if __name__ == "__main__":
    unittest.main()
