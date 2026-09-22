import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from art_pipeline import studio_store as store
from art_pipeline import studio_worker as worker
from art_pipeline.studio_candidates import register_candidate
from art_pipeline.studio_production import apply_decision


class StateTests(unittest.TestCase):
    def setUp(self):
        self.old = {
            "state": store.STATE_FILE,
            "reviews": store.REVIEWS_FILE,
            "web": store.WEB_DIR,
            "approved": store.APPROVED_ROOT,
            "load_tome": store.load_tome,
            "script": worker.GENERATOR_SCRIPT,
            "log": worker.GENERATOR_LOG,
            "process": worker._GENERATION_PROCESS,
        }
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        store.STATE_FILE = base / "state.json"
        store.REVIEWS_FILE = base / "reviews.jsonl"
        store.WEB_DIR = base / "web"
        store.APPROVED_ROOT = store.WEB_DIR / "approved"
        worker.GENERATOR_SCRIPT = base / "generate.py"
        worker.GENERATOR_SCRIPT.write_text("print('test')\n", encoding="utf-8")
        worker.GENERATOR_LOG = base / "worker.log"
        worker._GENERATION_PROCESS = None
        (store.WEB_DIR / "candidates").mkdir(parents=True, exist_ok=True)
        store.write_json(store.STATE_FILE, {
            "current_page_id": "I-01",
            "updated_at": "test",
            "complete": False,
            "pages": {
                "I-01": {"status": "queued", "attempt": 0, "current_candidate": None, "attempt_history": []},
                "I-02": {"status": "planned", "attempt": 0, "current_candidate": None, "attempt_history": []},
            },
        })
        store.load_tome = lambda: {
            "tome_id": "TOME-I",
            "title": "Caves & Dungeons",
            "theme": "test",
            "total_pages": 2,
            "pages": [
                {"page_id": "I-01", "order": 1, "monster_name": "Kobold", "monster_spec_id": "kobold-warrior"},
                {"page_id": "I-02", "order": 2, "monster_name": "Goblin", "monster_spec_id": "goblin-minion"},
            ],
        }

    def tearDown(self):
        store.STATE_FILE = self.old["state"]
        store.REVIEWS_FILE = self.old["reviews"]
        store.WEB_DIR = self.old["web"]
        store.APPROVED_ROOT = self.old["approved"]
        store.load_tome = self.old["load_tome"]
        worker.GENERATOR_SCRIPT = self.old["script"]
        worker.GENERATOR_LOG = self.old["log"]
        worker._GENERATION_PROCESS = self.old["process"]
        self.temp.cleanup()

    def test_cannot_approve_without_candidate(self):
        with self.assertRaises(ValueError):
            apply_decision("approve")

    def test_register_candidate_then_approve_archives_and_advances(self):
        candidate = store.WEB_DIR / "candidates" / "test.png"
        candidate.write_bytes(b"fake-png-for-copy-test")
        register_candidate({"page_id": "I-01", "image_path": "candidates/test.png"})
        result = apply_decision("approve")
        self.assertEqual(result["current_page_id"], "I-02")
        state = store.load_state()
        self.assertEqual(state["pages"]["I-01"]["status"], "locked")
        self.assertEqual(state["pages"]["I-02"]["status"], "queued")
        approved = store.WEB_DIR / "approved" / "Tome-I" / "I-01.png"
        self.assertEqual(approved.read_bytes(), candidate.read_bytes())

    def test_approve_activates_ordered_rebuild_source(self):
        first = store.WEB_DIR / "candidates" / "first.png"
        first.write_bytes(b"first")
        rebuild = store.WEB_DIR / "candidates" / "rebuild" / "I-02-source.png"
        rebuild.parent.mkdir(parents=True, exist_ok=True)
        rebuild.write_bytes(b"second")
        state = store.load_state()
        state["pages"]["I-02"]["rebuild_source_path"] = "candidates/rebuild/I-02-source.png"
        store.write_json(store.STATE_FILE, state)

        register_candidate({"page_id": "I-01", "image_path": "candidates/first.png"})
        apply_decision("approve")
        second = store.load_state()["pages"]["I-02"]
        self.assertEqual(second["status"], "awaiting_human")
        self.assertEqual(second["current_candidate"]["generation_mode"], "rebuild_source")

    def test_modify_never_advances(self):
        register_candidate({"page_id": "I-01", "image_path": "candidates/test.png"})
        apply_decision("modify", "simplify walls", ["more white space"])
        state = store.load_state()
        self.assertEqual(state["current_page_id"], "I-01")
        self.assertEqual(state["pages"]["I-01"]["status"], "modify_requested")

    def test_reject_candidate_for_future_page(self):
        with self.assertRaises(ValueError):
            register_candidate({"page_id": "I-02", "image_path": "candidates/test.png"})

    @patch("art_pipeline.studio_worker.subprocess.Popen")
    def test_generation_worker_starts_once(self, popen):
        process = Mock()
        process.pid = 4321
        process.poll.return_value = None
        popen.return_value = process
        first = worker.start_generation_worker()
        second = worker.start_generation_worker()
        self.assertTrue(first["started"])
        self.assertFalse(second["started"])
        self.assertEqual(popen.call_count, 1)

    @patch("art_pipeline.studio_worker.subprocess.Popen")
    def test_generation_worker_refuses_missing_spec(self, popen):
        tome = store.load_tome()
        tome["pages"][0].pop("monster_spec_id", None)
        store.load_tome = lambda: tome
        result = worker.start_generation_worker()
        self.assertFalse(result["started"])
        self.assertEqual(result["reason"], "canonical_monster_spec_required")
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
