import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from equipment_attachments import attachment_assignments
from equipment_policy import canonical_weapon_gear, load_equipment_rules
from monster_catalog import resolve_monster_spec


class EquipmentCatalogPolicyTests(unittest.TestCase):
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
