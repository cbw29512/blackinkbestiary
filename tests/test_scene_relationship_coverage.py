import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from scene_relationships import active_relationship_rules


class SceneRelationshipCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        cls.pages = {page["page_id"]: page for page in tome["pages"]}

    def rule_ids(self, page_id: str) -> set[str]:
        return {
            item["rule_id"]
            for item in active_relationship_rules(self.pages[page_id], ROOT)
        }

    def test_offering_object_stays_in_contact_with_fingers(self):
        rules = active_relationship_rules(self.pages["I-02"], ROOT)
        offering = next(item for item in rules if item["rule_id"] == "offering_to_shrine")
        text = " ".join(offering["directives"])
        self.assertIn("held, pinched, or supported by the fingers", text)
        self.assertIn("must not float", text)

    def test_map_dagger_has_pinning_contact_rule(self):
        self.assertIn("pinning_to_surface", self.rule_ids("I-07"))

    def test_kicked_lantern_suppresses_mounted_fixture_state(self):
        ids = self.rule_ids("I-04")
        self.assertIn("dislodging_fixture", ids)
        self.assertIn("interaction_contact", ids)
        self.assertNotIn("wall_mounted_fixture", ids)

    def test_wedged_ogre_has_two_surface_contact_rule(self):
        self.assertIn("wedged_between_surfaces", self.rule_ids("I-10"))

    def test_peeling_creatures_keep_support_contact(self):
        self.assertIn("peeling_from_support", self.rule_ids("I-14"))
        self.assertIn("peeling_from_support", self.rule_ids("I-36"))

    def test_opening_emergence_covers_swarm_grate_and_bulette(self):
        self.assertIn("emerging_from_opening", self.rule_ids("I-17"))
        self.assertIn("emerging_from_opening", self.rule_ids("I-19"))
        self.assertIn("emerging_from_opening", self.rule_ids("I-39"))

    def test_defending_nest_maps_to_guarding_relationship(self):
        self.assertIn("guarding_focal_object", self.rule_ids("I-18"))

    def test_wrapping_contact_covers_centipede_rug_and_behir(self):
        self.assertIn("wrapped_around_target", self.rule_ids("I-20"))
        self.assertIn("wrapped_around_target", self.rule_ids("I-31"))
        self.assertIn("wrapped_around_target", self.rule_ids("I-47"))

    def test_spider_support_rules_are_explicit(self):
        self.assertIn("web_supported", self.rule_ids("I-22"))
        self.assertIn("ceiling_cling", self.rule_ids("I-23"))

    def test_corrosion_is_tied_to_contact_point(self):
        self.assertIn("corrosive_contact", self.rule_ids("I-25"))

    def test_stepping_down_keeps_visible_support(self):
        self.assertIn("stepping_from_support", self.rule_ids("I-29"))


if __name__ == "__main__":
    unittest.main()
