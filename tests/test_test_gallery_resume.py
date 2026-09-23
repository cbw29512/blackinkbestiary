import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_test_gallery.py"
spec = importlib.util.spec_from_file_location("generate_test_gallery", SCRIPT)
gallery = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(gallery)


class TestGalleryResumeTests(unittest.TestCase):
    def test_existing_success_is_skipped(self):
        prior = {"status": "ready_for_review"}
        self.assertTrue(gallery.should_skip_candidate(prior, False))
        self.assertTrue(gallery.should_skip_candidate(prior, True))

    def test_failed_candidate_can_be_retried(self):
        prior = {"status": "technical_qa_failed"}
        self.assertTrue(gallery.should_skip_candidate(prior, False))
        self.assertFalse(gallery.should_skip_candidate(prior, True))

    def test_resume_preserves_results_and_selections(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "state.json"
            state_path.write_text(json.dumps({
                "schema_version": 2,
                "copies_per_page": 2,
                "results": [{"page_id": "I-01", "candidate": 1, "status": "ready_for_review"}],
                "selections": {"I-01": {"candidate": 1}},
                "completed_at": "old"
            }), encoding="utf-8")
            with patch.object(gallery, "STATE_FILE", state_path):
                state = gallery.load_or_init_state(4, False)
            self.assertEqual(state["copies_per_page"], 4)
            self.assertEqual(len(state["results"]), 1)
            self.assertEqual(state["selections"]["I-01"]["candidate"], 1)
            self.assertNotIn("completed_at", state)


if __name__ == "__main__":
    unittest.main()
