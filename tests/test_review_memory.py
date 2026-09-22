import json
import tempfile
import unittest
from pathlib import Path

import server


class ReviewMemoryTests(unittest.TestCase):
    def setUp(self):
        self.old_state = server.STATE_FILE
        self.old_reviews = server.REVIEWS_FILE
        self.old_load_tome = server.load_tome
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        server.STATE_FILE = base / "state.json"
        server.REVIEWS_FILE = base / "reviews.jsonl"
        server.write_json(server.STATE_FILE, {
            "current_page_id": "I-01",
            "updated_at": "test",
            "complete": False,
            "pages": {
                "I-01": {
                    "status": "queued",
                    "attempt": 0,
                    "current_candidate": None,
                    "attempt_history": [],
                }
            },
        })
        server.load_tome = lambda: {
            "tome_id": "TEST-BOOK",
            "title": "Test Book",
            "theme": "test",
            "total_pages": 1,
            "pages": [{
                "page_id": "I-01",
                "order": 1,
                "monster_name": "Kobold Warrior",
                "monster_spec_id": "kobold-warrior",
                "archetype": "trap_scene",
            }],
        }

    def tearDown(self):
        server.STATE_FILE = self.old_state
        server.REVIEWS_FILE = self.old_reviews
        server.load_tome = self.old_load_tome
        self.temp.cleanup()

    def test_composition_defect_routes_modify_to_regenerate(self):
        server.register_candidate({
            "page_id": "I-01",
            "image_path": "candidates/test.png",
            "generation_mode": "text_to_image",
        })
        server.apply_decision("modify", "composition is fundamentally wrong", ["composition wrong"])

        state = server.load_state()
        self.assertEqual(state["pages"]["I-01"]["status"], "regenerate_requested")
        record = json.loads(server.REVIEWS_FILE.read_text(encoding="utf-8").strip())
        self.assertEqual(record["requested_decision"], "modify")
        self.assertEqual(record["decision"], "regenerate")
        self.assertEqual(record["routing_recommendation"], "regenerate")

    def test_modify_records_structured_defect_intelligence(self):
        server.register_candidate({
            "page_id": "I-01",
            "image_path": "candidates/test.png",
            "generation_mode": "text_to_image",
        })
        server.apply_decision(
            "modify",
            "make the trap easier to read",
            ["story beat unclear", "pose too stiff"],
        )

        record = json.loads(server.REVIEWS_FILE.read_text(encoding="utf-8").strip())
        self.assertEqual(record["book_id"], "TEST-BOOK")
        self.assertEqual(record["archetype"], "trap_scene")
        self.assertEqual(record["routing_recommendation"], "modify")
        self.assertEqual(record["quick_tags"], ["story beat unclear", "pose too stiff"])
        self.assertEqual(record["failed_dimensions"], ["story_moment"])
        self.assertIn("colorability", record["preserve_dimensions"])
        self.assertIn("monster_identity", record["preserve_dimensions"])
        self.assertEqual(len(record["remediation_directives"]), 2)
        self.assertIn("cause-and-effect", record["remediation_directives"][0])

        state = server.load_state()
        notes = state["pages"]["I-01"]["review_notes"]
        self.assertEqual(notes["failed_dimensions"], ["story_moment"])
        self.assertIn("environment_identity", notes["preserve_dimensions"])


if __name__ == "__main__":
    unittest.main()
