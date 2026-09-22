import json
import tempfile
import unittest
from pathlib import Path

from art_pipeline import studio_store as store
from art_pipeline.studio_candidates import register_candidate
from art_pipeline.studio_production import apply_decision


class ReviewMemoryTests(unittest.TestCase):
    def setUp(self):
        self.old_state = store.STATE_FILE
        self.old_reviews = store.REVIEWS_FILE
        self.old_load_tome = store.load_tome
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        store.STATE_FILE = base / "state.json"
        store.REVIEWS_FILE = base / "reviews.jsonl"
        store.write_json(store.STATE_FILE, {
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
        store.load_tome = lambda: {
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
                "environment": {
                    "identity": "trapped stone corridor",
                    "anchors": ["tripwire", "punji pit"],
                },
            }],
        }

    def tearDown(self):
        store.STATE_FILE = self.old_state
        store.REVIEWS_FILE = self.old_reviews
        store.load_tome = self.old_load_tome
        self.temp.cleanup()

    def _candidate(self):
        register_candidate({
            "page_id": "I-01",
            "image_path": "candidates/test.png",
            "generation_mode": "text_to_image",
        })

    def test_composition_defect_routes_modify_to_regenerate(self):
        self._candidate()
        apply_decision("modify", "composition is fundamentally wrong", ["composition wrong"])
        state = store.load_state()
        self.assertEqual(state["pages"]["I-01"]["status"], "regenerate_requested")
        record = json.loads(store.REVIEWS_FILE.read_text(encoding="utf-8").strip())
        self.assertEqual(record["requested_decision"], "modify")
        self.assertEqual(record["decision"], "regenerate")

    def test_environment_defect_is_recorded_with_environment_context(self):
        self._candidate()
        apply_decision(
            "modify",
            "make the corridor part of the trap",
            ["stronger environment identity", "environment story disconnected"],
        )
        record = json.loads(store.REVIEWS_FILE.read_text(encoding="utf-8").strip())
        self.assertEqual(record["environment_identity"], "trapped stone corridor")
        self.assertEqual(record["environment_anchors"], ["tripwire", "punji pit"])
        self.assertEqual(record["routing_recommendation"], "modify")
        self.assertEqual(len(record["remediation_directives"]), 2)


if __name__ == "__main__":
    unittest.main()
