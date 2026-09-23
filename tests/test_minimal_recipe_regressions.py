import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from page_contract import load_page_contract
from prompt_builder import build_prompt
from scene_relationships import active_relationship_rules


class MinimalRecipeRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tome = json.loads(
            (ROOT / "data" / "tome-I.json").read_text(encoding="utf-8")
        )
        cls.pages = {page["page_id"]: page for page in cls.tome["pages"]}

    def test_tome_i_uses_only_allowed_recipe_fields(self):
        contract = load_page_contract(ROOT / "config" / "universal_page_contract.json")
        allowed = set(contract["allowed_source_fields"])
        self.assertEqual(len(self.tome["pages"]), 50)
        for page in self.tome["pages"]:
            self.assertEqual(set(page) - allowed, set(), page["page_id"])
            self.assertNotIn("page_exceptions", page, page["page_id"])

    def test_golden_five_keep_story_critical_information(self):
        expectations = {
            "I-01": ["tripwire", "punji pit", "torch bracket"],
            "I-24": ["bones and a key", "suspended inside"],
            "I-27": ["reaching hand", "toothed mouth"],
            "I-38": ["ankheg", "bursts upward", "loose floor"],
            "I-40": ["rust monster", "damaged metal pile", "weapon rack"],
        }
        for page_id, phrases in expectations.items():
            text = build_prompt(self.pages[page_id]).lower()
            for phrase in phrases:
                self.assertIn(phrase.lower(), text, f"{page_id}: {phrase}")

    def test_relationship_budget_keeps_critical_trap_rules(self):
        page = {
            "moment": "carrying a sack while a tripwire triggers a pit",
            "archetype": "trap_scene",
            "environment_variant": {
                "landmark": "wall torch beside a pressure plate and open pit",
                "framing": "tight corridor",
                "interaction": "pulls the tripwire while guarding the route",
            },
            "physicality": {
                "mode": "grounded",
                "support": "feet on floor",
                "motion": "pulling the trigger",
            },
        }
        ids = [item["rule_id"] for item in active_relationship_rules(page, ROOT)]
        self.assertEqual(len(ids), 4)
        self.assertIn("tripwire_trigger", ids)
        self.assertIn("pit_interrupts_route", ids)
        self.assertIn("pressure_plate_route", ids)
        self.assertIn("interaction_contact", ids)


    def test_i24_containment_does_not_trigger_hanging_support(self):
        rules = active_relationship_rules(self.pages["I-24"], ROOT)
        ids = [item["rule_id"] for item in rules]
        self.assertIn("contained_inside_body", ids)
        self.assertNotIn("hanging_from_support", ids)

    def test_i27_reaching_hand_gets_contact_relationship(self):
        ids = [item["rule_id"] for item in active_relationship_rules(self.pages["I-27"], ROOT)]
        self.assertIn("interaction_contact", ids)

    def test_i38_bursting_from_ground_gets_emergence_relationship(self):
        ids = [item["rule_id"] for item in active_relationship_rules(self.pages["I-38"], ROOT)]
        self.assertIn("emerging_from_opening", ids)

    def test_i40_feeding_story_gets_physical_contact_relationship(self):
        ids = [item["rule_id"] for item in active_relationship_rules(self.pages["I-40"], ROOT)]
        self.assertIn("feeding_contact", ids)


    def test_relationship_rules_ignore_incidental_words(self):
        cases = {
            "I-12": "pit_interrupts_route",
            "I-18": "carrying_object",
            "I-26": "interaction_contact",
            "I-37": "interaction_contact",
            "I-41": "pit_interrupts_route",
            "I-45": "carrying_object",
        }
        for page_id, forbidden_rule in cases.items():
            ids = [
                item["rule_id"]
                for item in active_relationship_rules(self.pages[page_id], ROOT)
            ]
            self.assertNotIn(forbidden_rule, ids, page_id)

    def test_no_duplicate_required_object_rule_section(self):
        text = build_prompt(self.pages["I-01"])
        self.assertNotIn("REQUIRED OBJECT PHYSICAL RULES", text)


if __name__ == "__main__":
    unittest.main()
