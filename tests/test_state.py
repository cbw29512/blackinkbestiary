import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import server


class StateTests(unittest.TestCase):
    def setUp(self):
        self.old_state = server.STATE_FILE
        self.old_reviews = server.REVIEWS_FILE
        self.old_web_dir = server.WEB_DIR
        self.old_approved_root = server.APPROVED_ROOT
        self.old_load_tome = server.load_tome
        self.old_generator_script = server.GENERATOR_SCRIPT
        self.old_generator_log = server.GENERATOR_LOG
        self.old_generation_process = server._GENERATION_PROCESS
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        server.STATE_FILE = base / "state.json"
        server.REVIEWS_FILE = base / "reviews.jsonl"
        server.WEB_DIR = base / "web"
        server.APPROVED_ROOT = server.WEB_DIR / "approved"
        server.GENERATOR_SCRIPT = base / "generate.py"
        server.GENERATOR_SCRIPT.write_text("print('test')\n", encoding="utf-8")
        server.GENERATOR_LOG = base / "worker.log"
        server._GENERATION_PROCESS = None
        (server.WEB_DIR / "candidates").mkdir(parents=True, exist_ok=True)
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
                {"page_id": "I-01", "order": 1, "monster_name": "Kobold", "monster_spec_id": "kobold-warrior"},
                {"page_id": "I-02", "order": 2, "monster_name": "Goblin", "monster_spec_id": "goblin-minion"},
            ],
        }

    def tearDown(self):
        server.STATE_FILE = self.old_state
        server.REVIEWS_FILE = self.old_reviews
        server.WEB_DIR = self.old_web_dir
        server.APPROVED_ROOT = self.old_approved_root
        server.GENERATOR_SCRIPT = self.old_generator_script
        server.GENERATOR_LOG = self.old_generator_log
        server._GENERATION_PROCESS = self.old_generation_process
        server.load_tome = self.old_load_tome
        self.temp.cleanup()

    def test_cannot_approve_without_candidate(self):
        with self.assertRaises(ValueError):
            server.apply_decision("approve")

    def test_register_candidate_then_approve_archives_and_advances_one_page(self):
        candidate = server.WEB_DIR / "candidates" / "test.png"
        candidate.write_bytes(b"fake-png-for-copy-test")
        server.register_candidate({"page_id": "I-01", "image_path": "candidates/test.png"})
        result = server.apply_decision("approve")
        self.assertEqual(result["current_page_id"], "I-02")
        state = server.load_state()
        self.assertEqual(state["pages"]["I-01"]["status"], "locked")
        self.assertEqual(state["pages"]["I-01"]["approved_image_path"], "approved/Tome-I/I-01.png")
        self.assertEqual(state["pages"]["I-02"]["status"], "queued")
        approved = server.WEB_DIR / "approved" / "Tome-I" / "I-01.png"
        self.assertTrue(approved.exists())
        self.assertEqual(approved.read_bytes(), candidate.read_bytes())


    def test_approve_activates_ordered_rebuild_source(self):
        first = server.WEB_DIR / "candidates" / "first.png"
        first.write_bytes(b"first")
        rebuild = server.WEB_DIR / "candidates" / "rebuild" / "I-02-source.png"
        rebuild.parent.mkdir(parents=True, exist_ok=True)
        rebuild.write_bytes(b"second")

        state = server.load_state()
        state["pages"]["I-02"]["rebuild_source_path"] = "candidates/rebuild/I-02-source.png"
        server.write_json(server.STATE_FILE, state)

        server.register_candidate({"page_id": "I-01", "image_path": "candidates/first.png"})
        result = server.apply_decision("approve")

        self.assertEqual(result["current_page_id"], "I-02")
        state = server.load_state()
        second = state["pages"]["I-02"]
        self.assertEqual(second["status"], "awaiting_human")
        self.assertEqual(second["current_candidate"]["generation_mode"], "rebuild_source")
        self.assertEqual(second["current_candidate"]["image_path"], "candidates/rebuild/I-02-source.png")

    def test_approve_refuses_to_overwrite_different_locked_art_file(self):
        candidate = server.WEB_DIR / "candidates" / "test.png"
        candidate.write_bytes(b"new-art")
        approved = server.WEB_DIR / "approved" / "Tome-I" / "I-01.png"
        approved.parent.mkdir(parents=True, exist_ok=True)
        approved.write_bytes(b"old-art")
        server.register_candidate({"page_id": "I-01", "image_path": "candidates/test.png"})
        with self.assertRaises(ValueError):
            server.apply_decision("approve")
        state = server.load_state()
        self.assertEqual(state["current_page_id"], "I-01")
        self.assertEqual(state["pages"]["I-01"]["status"], "awaiting_human")
        self.assertEqual(approved.read_bytes(), b"old-art")

    def test_modify_never_advances(self):
        server.register_candidate({"page_id": "I-01", "image_path": "candidates/test.png"})
        server.apply_decision("modify", "simplify walls", ["more white space"])
        state = server.load_state()
        self.assertEqual(state["current_page_id"], "I-01")
        self.assertEqual(state["pages"]["I-01"]["status"], "modify_requested")

    def test_reject_candidate_for_future_page(self):
        with self.assertRaises(ValueError):
            server.register_candidate({"page_id": "I-02", "image_path": "candidates/test.png"})

    @patch("server.local_generation_preflight")
    @patch("server.subprocess.Popen")
    def test_generation_worker_starts_once_for_current_spec_page(self, popen, preflight):
        preflight.return_value = {"ready_for_generation": True}
        process = Mock()
        process.pid = 4321
        process.poll.return_value = None
        popen.return_value = process

        first = server.start_generation_worker()
        second = server.start_generation_worker()

        self.assertTrue(first["started"])
        self.assertFalse(second["started"])
        self.assertEqual(popen.call_count, 1)
        argv = popen.call_args.args[0]
        self.assertEqual(Path(argv[1]), server.GENERATOR_SCRIPT)

    @patch("server.local_generation_preflight")
    @patch("server.subprocess.Popen")
    def test_generation_worker_refuses_when_local_preflight_fails(self, popen, preflight):
        preflight.return_value = {
            "ready_for_generation": False,
            "required_models_missing": ["vae.safetensors"],
        }

        result = server.start_generation_worker()

        self.assertFalse(result["started"])
        self.assertEqual(result["reason"], "local_generation_preflight_failed")
        self.assertEqual(result["preflight"]["required_models_missing"], ["vae.safetensors"])
        popen.assert_not_called()

    @patch("server.subprocess.Popen")
    def test_generation_worker_refuses_page_without_canonical_spec(self, popen):
        tome = server.load_tome()
        tome["pages"][0].pop("monster_spec_id", None)
        server.load_tome = lambda: tome

        result = server.start_generation_worker()

        self.assertFalse(result["started"])
        self.assertEqual(result["reason"], "canonical_monster_spec_required")
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
