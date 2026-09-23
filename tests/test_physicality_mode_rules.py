import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from physicality_modes import resolve_mode_group, uncovered_modes
from physicality_prompt import physicality_sections


class PhysicalityModeRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        cls.pages = {page["page_id"]: page for page in cls.tome["pages"]}

    def test_every_tome_i_mode_has_one_universal_family(self):
        self.assertEqual(uncovered_modes(self.tome["pages"], ROOT), [])
        for page in self.tome["pages"]:
            mode = page["physicality"]["mode"]
            group = resolve_mode_group(mode, ROOT)
            self.assertIsNotNone(group, page["page_id"])

    def test_grounded_page_gets_load_bearing_support_rule(self):
        text = " ".join(physicality_sections(self.pages["I-01"]))
        self.assertIn("UNIVERSAL PHYSICALITY — STABLE GROUND", text)
        self.assertIn("load-bearing", text)

    def test_peeling_page_gets_attached_support_rule(self):
        text = " ".join(physicality_sections(self.pages["I-14"]))
        self.assertIn("UNIVERSAL PHYSICALITY — ATTACHED SUPPORT", text)
        self.assertIn("attachment/contact points", text)

    def test_burrowing_page_gets_embedded_support_rule(self):
        text = " ".join(physicality_sections(self.pages["I-39"]))
        self.assertIn("UNIVERSAL PHYSICALITY — EMBEDDED OR EMERGING", text)
        self.assertIn("source opening", text)

    def test_ooze_page_gets_continuous_contact_rule(self):
        text = " ".join(physicality_sections(self.pages["I-25"]))
        self.assertIn("UNIVERSAL PHYSICALITY — OOZE CONTACT", text)
        self.assertIn("continuous contact path", text)

    def test_magical_flight_stays_intentionally_airborne(self):
        text = " ".join(physicality_sections(self.pages["I-30"]))
        self.assertIn("UNIVERSAL PHYSICALITY — INTENTIONAL AIRBORNE", text)
        self.assertIn("magical locomotion", text)


if __name__ == "__main__":
    unittest.main()
