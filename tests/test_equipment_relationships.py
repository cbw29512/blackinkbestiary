import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from equipment_relationships import held_weapon_gear
from monster_catalog import resolve_monster_spec
from prompt_builder import build_prompt, build_supervisor_checklist


class EquipmentRelationshipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        cls.i01 = next(page for page in tome["pages"] if page["page_id"] == "I-01")

    def test_kobold_weapon_inherits_universal_hand_contact_rule(self):
        spec = resolve_monster_spec("kobold-warrior")
        self.assertEqual(held_weapon_gear(spec, self.i01, ROOT), ["short simple spear"])

        text = build_prompt(self.i01)
        self.assertIn("CREATURE EQUIPMENT RELATIONSHIP — HELD WEAPON", text)
        self.assertIn("short simple spear", text)
        self.assertIn("grasping hand or limb", text)
        self.assertIn("one instance of each canonical carried weapon", text)

    def test_explicitly_detached_weapon_does_not_require_hand_contact(self):
        page = deepcopy(self.i01)
        page["moment"] = "Watching a short spear displayed on a wall rack"
        page["environment_variant"]["interaction"] = (
            "kobold stands beside the short spear displayed on a wall rack"
        )
        spec = resolve_monster_spec("kobold-warrior")

        self.assertEqual(held_weapon_gear(spec, page, ROOT), [])
        self.assertNotIn(
            "CREATURE EQUIPMENT RELATIONSHIP — HELD WEAPON",
            build_prompt(page),
        )

    def test_supervisor_checks_weapon_contact_and_duplication(self):
        checks = build_supervisor_checklist(self.i01)
        joined = " ".join(checks)
        self.assertIn("Weapon contact (short simple spear)", joined)
        self.assertIn("visibly contacts a grasping hand or limb", joined)
        self.assertIn("not duplicated", joined)


if __name__ == "__main__":
    unittest.main()
