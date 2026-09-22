import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from environment_spec import checklist, prompt_sections, validate_environment
from quality_system import expand_defect_tags, recommended_action


class EnvironmentQualityTests(unittest.TestCase):
    def setUp(self):
        self.tome = json.loads(
            (ROOT / "data" / "tome-I.json").read_text(encoding="utf-8")
        )

    def test_every_page_has_structured_environment(self):
        self.assertEqual(len(self.tome["pages"]), 50)
        for page in self.tome["pages"]:
            self.assertEqual(validate_environment(page), [], page["page_id"])
            env = page["environment"]
            self.assertGreaterEqual(len(env["anchors"]), 2, page["page_id"])
            self.assertTrue(env["interaction"].strip(), page["page_id"])

    def test_environment_prompt_is_not_background_filler(self):
        sections = prompt_sections(self.tome["pages"][0])
        text = "\n".join(sections)
        self.assertIn("CO-EQUAL STORYTELLING SUBJECT", text)
        self.assertIn("recognizable even if the monster were hidden", text)
        self.assertIn("visible tripwire", text)

    def test_environment_checklist_audits_anchors_and_interaction(self):
        checks = checklist(self.tome["pages"][0])
        text = "\n".join(checks)
        self.assertIn("Environment anchor present", text)
        self.assertIn("interact visibly", text)

    def test_environment_defects_expand_to_targeted_repairs(self):
        directives = expand_defect_tags(
            ROOT,
            ["environment too generic", "environment story disconnected"],
        )
        self.assertEqual(len(directives), 2)
        self.assertIn("specific environmental anchors", directives[0])
        self.assertIn("physically interact", directives[1])

    def test_wrong_environment_routes_to_regenerate(self):
        self.assertEqual(
            recommended_action(ROOT, ["wrong environment"]),
            "regenerate",
        )


if __name__ == "__main__":
    unittest.main()
