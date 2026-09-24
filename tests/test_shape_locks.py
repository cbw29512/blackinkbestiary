import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from prompt_builder import build_prompt, build_supervisor_checklist


class ShapeLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        cls.pages = {page["page_id"]: page for page in tome["pages"]}

    def test_kobold_shape_lock_proves_miniature_scale(self):
        text = build_prompt(self.pages["I-01"])
        self.assertIn("SHAPE-FIRST RENDER LOCK", text)
        self.assertIn("human-scale doorway or trap fixture", text)
        self.assertIn("more than twice the creature's height", text)

    def test_darkmantle_shape_lock_forbids_humanoid_topology(self):
        text = build_prompt(self.pages["I-14"])
        self.assertIn("one continuous non-humanoid mantle body", text)
        self.assertIn("no separate torso", text)
        self.assertIn("flight capability never invents wings", text)

    def test_bat_and_centipede_shape_locks_are_literal(self):
        bat = build_prompt(self.pages["I-16"])
        centipede = build_prompt(self.pages["I-20"])
        self.assertIn("exactly four limbs total", bat)
        self.assertIn("two forelimbs that ARE the membrane wings", bat)
        self.assertIn("every visible trunk segment carries exactly one pair", centipede)

    def test_shape_lock_is_an_identity_review_gate(self):
        checks = build_supervisor_checklist(self.pages["I-14"])
        self.assertTrue(any(item.startswith("Shape-first body geometry reads as:") for item in checks))


if __name__ == "__main__":
    unittest.main()
