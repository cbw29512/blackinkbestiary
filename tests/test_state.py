import tempfile
import unittest
from pathlib import Path

import server


class StateTests(unittest.TestCase):
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
                "I-01": {"status": "queued", "attempt": 0, "current_candidate": None, "attempt_history": []},
                "I-02": {"status": "planned", "attempt": 0, "current_candidate": None, "attempt_history": []},
            },
        })
        server.load_tome = lambda: {
            "tome_id": "TOME-I",
            "title": "Caves & Dungeons",
            "theme": "test",
            "total_pages": 2,
            "pages": [
                {"page_id": "I-01", "order": 1, "monster_name": "Kobold"},
                {"page_id": "I-02", "order": 2, "monster_name": "Goblin"},
            ],
        }

    def tearDown(self):
        server.STATE_FILE = self.old_state
        server.REVIEWS_FILE = self.old_reviews
        server.load_tome = self.old_load_tome
        self.temp.cleanup()

    def test_cannot_approve_without_candidate(self):
        with self.assertRaises(ValueError):
            server.apply_decision("approve")

    def test_register_candidate_then_approve_advances_one_page(self):
        server.register_candidate({"page_id": "I-01", "image_path": "candidates/test.png"})
        result = server.apply_decision("approve")
        self.assertEqual(result["current_page_id"], "I-02")
        state = server.load_state()
        self.assertEqual(state["pages"]["I-01"]["status"], "locked")
        self.assertEqual(state["pages"]["I-02"]["status"], "queued")

    def test_modify_never_advances(self):
        server.register_candidate({"page_id": "I-01", "image_path": "candidates/test.png"})
        server.apply_decision("modify", "simplify walls", ["more white space"])
        state = server.load_state()
        self.assertEqual(state["current_page_id"], "I-01")
        self.assertEqual(state["pages"]["I-01"]["status"], "modify_requested")

    def test_reject_candidate_for_future_page(self):
        with self.assertRaises(ValueError):
            server.register_candidate({"page_id": "I-02", "image_path": "candidates/test.png"})


if __name__ == "__main__":
    unittest.main()
