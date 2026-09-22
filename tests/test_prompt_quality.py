import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from edit_prompt import build_edit_prompt
from prompt_builder import build_prompt, load_monster_spec


def environment(identity: str) -> dict:
    return {
        "identity": identity,
        "anchors": ["stone walls", "story prop"],
        "interaction": "the creature visibly uses the setting during the action",
        "coloring_value": ["large wall planes", "open floor shapes"],
        "must_avoid": ["generic empty backdrop"],
    }


class PromptTests(unittest.TestCase):
    def test_prompt_contains_three_equal_quality_gates(self):
        page = {
            "monster_name": "Kobold Warrior",
            "habitat": "trapped corridor",
            "environment": environment("trapped dressed-stone corridor"),
            "moment": "tripwire triggered",
            "identity_rules": ["snout", "horn nubs"],
            "must_include": ["pit"],
            "must_avoid": ["gray"],
            "composition": "portrait",
        }
        text = build_prompt(page)
        self.assertIn("Kobold Warrior", text)
        self.assertIn("ENVIRONMENT IS A CO-EQUAL STORYTELLING SUBJECT", text)
        self.assertIn("trapped dressed-stone corridor", text)
        self.assertIn("Final three-gate test", text)

    def test_edit_prompt_preserves_environment_and_art(self):
        page = {
            "monster_name": "Goblin Minion",
            "habitat": "dungeon pantry",
            "environment": environment("rough medieval dungeon pantry"),
            "moment": "running away with a stolen ham",
            "identity_rules": [],
            "must_include": ["stolen ham"],
            "must_avoid": ["modern kitchen"],
            "composition": "portrait",
        }
        text = build_edit_prompt(
            page,
            {
                "text": "make the ham obvious",
                "quick_tags": ["stronger environment identity"],
            },
        )
        self.assertIn("EDIT THE PROVIDED CURRENT COLORING PAGE", text)
        self.assertIn("Preserve successful environment anchors", text)
        self.assertIn("make the ham obvious", text)
        self.assertIn("Strengthen the setting", text)

    def test_first_five_pages_resolve_canonical_specs(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        for page in tome["pages"][:5]:
            spec = load_monster_spec(page)
            self.assertEqual(spec["monster_id"], page["monster_spec_id"])
            self.assertTrue(spec["visual_identity"]["must_keep"])
            self.assertTrue(spec["accuracy_checks"])

    def test_canonical_kobold_and_environment_enter_prompt(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        text = build_prompt(tome["pages"][0])
        self.assertIn("CANONICAL SILHOUETTE", text)
        self.assertIn("long balancing tail", text)
        self.assertIn("visible tripwire anchored across the passage", text)
        self.assertIn("monster and environment visibly interact", text.lower())

    def test_review_notes_and_environment_defects_enter_prompt(self):
        page = {
            "monster_name": "Kobold",
            "habitat": "cave",
            "environment": environment("specific cave ambush chamber"),
            "moment": "waiting",
            "identity_rules": [],
            "must_include": [],
            "must_avoid": [],
            "composition": "portrait",
        }
        text = build_prompt(
            page,
            {
                "text": "improve the cave",
                "quick_tags": ["environment too generic"],
            },
        )
        self.assertIn("improve the cave", text)
        self.assertIn("Replace generic walls", text)


if __name__ == "__main__":
    unittest.main()
