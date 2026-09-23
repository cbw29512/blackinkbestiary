import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from equipment_attachments import attachment_assignments
from equipment_policy import canonical_weapon_gear, load_equipment_rules
from equipment_relationships import held_weapon_gear, secured_weapon_gear
from monster_catalog import resolve_monster_spec
from prompt_builder import build_prompt, build_supervisor_checklist


class EquipmentRelationshipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        cls.pages = {page["page_id"]: page for page in tome["pages"]}

    def test_kobold_weapon_is_held_in_one_real_grip(self):
        spec = resolve_monster_spec("kobold-warrior")
        page = self.pages["I-01"]
        self.assertEqual(held_weapon_gear(spec, page, ROOT), ["short simple spear"])
        self.assertEqual(secured_weapon_gear(spec, page, ROOT), [])
        text = build_prompt(page)
        self.assertIn("CREATURE EQUIPMENT RELATIONSHIP — HELD", text)
        self.assertIn("grasping hand or limb", text)
        self.assertIn("one instance of each canonical carried weapon", text)

    def test_externally_displayed_weapon_is_not_forced_onto_creature(self):
        page = deepcopy(self.pages["I-01"])
        page["moment"] = "Watching a short spear displayed on a wall rack"
        page["environment_variant"]["interaction"] = (
            "kobold stands beside the short spear displayed on a wall rack"
        )
        spec = resolve_monster_spec("kobold-warrior")
        self.assertEqual(held_weapon_gear(spec, page, ROOT), [])
        self.assertEqual(secured_weapon_gear(spec, page, ROOT), [])

    def test_busy_hands_secure_canonical_weapon(self):
        page = self.pages["I-03"]
        spec = resolve_monster_spec("goblin-minion")
        self.assertEqual(held_weapon_gear(spec, page, ROOT), [])
        self.assertEqual(
            secured_weapon_gear(spec, page, ROOT),
            ["belt-sheathed small scavenged knife"],
        )
        self.assertIn("CREATURE EQUIPMENT RELATIONSHIP — SECURED", build_prompt(page))

    def test_page_specific_weapon_overrides_busy_hand_default(self):
        page = self.pages["I-07"]
        spec = resolve_monster_spec("hobgoblin-captain")
        self.assertEqual(held_weapon_gear(spec, page, ROOT), ["dagger"])
        self.assertEqual(secured_weapon_gear(spec, page, ROOT), ["straight sword"])

    def test_weapon_creature_does_not_receive_hand_contact_rule(self):
        page = self.pages["I-30"]
        spec = resolve_monster_spec("flying-sword")
        self.assertEqual(held_weapon_gear(spec, page, ROOT), [])
        self.assertEqual(secured_weapon_gear(spec, page, ROOT), [])
        text = build_prompt(page)
        self.assertNotIn("CREATURE EQUIPMENT RELATIONSHIP — HELD", text)
        self.assertNotIn("CREATURE EQUIPMENT RELATIONSHIP — SECURED", text)

    def test_supervisor_checks_contact_duplication_and_scale(self):
        checks = " ".join(build_supervisor_checklist(self.pages["I-01"]))
        self.assertIn("Equipment contact (short simple spear)", checks)
        self.assertIn("visibly contacts a grasping hand or limb", checks)
        self.assertIn("not duplicated", checks)
        self.assertIn("subordinate", checks)


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
        assignments = {
            item["item"]: item["group_id"]
            for item in attachment_assignments(spec, ROOT)
        }
        self.assertEqual(assignments["rough leather straps"], "torso_gear")
        self.assertEqual(assignments["light scavenged armor"], "torso_gear")

    def test_ogre_belt_gets_waist_attachment(self):
        spec = resolve_monster_spec("ogre")
        assignments = {
            item["item"]: item["group_id"]
            for item in attachment_assignments(spec, ROOT)
        }
        self.assertEqual(assignments["thick belt"], "waist_gear")

    def test_zombie_restraints_get_real_attachment_points(self):
        spec = resolve_monster_spec("ogre-zombie")
        assignments = {
            item["item"]: item["group_id"]
            for item in attachment_assignments(spec, ROOT)
        }
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
