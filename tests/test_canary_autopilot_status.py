import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "canary_autopilot_status.py"
spec = importlib.util.spec_from_file_location("canary_autopilot_status", SCRIPT)
status = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(status)


class CanaryAutopilotStatusTests(unittest.TestCase):
    def test_ready_and_exhausted_pages_wait_for_exact_image_review(self):
        self.assertEqual(status.classify({"status": "ready_for_review"}), "awaiting_review")
        self.assertEqual(status.classify({"status": "max_refinements_reached"}), "awaiting_review")

    def test_exact_image_reject_reopens_generation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()[:16]
            item = {
                "page_id": "I-01",
                "candidate": 1,
                "status": "ready_for_review",
                "image_path": "test-gallery/I-01-C01.png",
                "assistant_review": {
                    "decision": "reject",
                    "review_id": f"I-01-C01-H{digest}",
                },
            }
            self.assertEqual(status.classify(item, root), "needs_generation")

    def test_exact_image_approval_is_terminal_for_current_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()[:16]
            item = {
                "page_id": "I-01",
                "candidate": 1,
                "status": "ready_for_review",
                "image_path": "test-gallery/I-01-C01.png",
                "assistant_review": {
                    "decision": "approve",
                    "review_id": f"I-01-C01-H{digest}",
                },
            }
            self.assertEqual(status.classify(item, root), "approved")

    def test_stale_approval_does_not_approve_changed_image(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"new-candidate")
            old_digest = hashlib.sha256(b"old-candidate").hexdigest()[:16]
            item = {
                "page_id": "I-01",
                "candidate": 1,
                "status": "ready_for_review",
                "image_path": "test-gallery/I-01-C01.png",
                "assistant_review": {
                    "decision": "approve",
                    "review_id": f"I-01-C01-H{old_digest}",
                },
            }
            self.assertEqual(status.classify(item, root), "awaiting_review")

    def test_missing_and_technical_failures_require_generation(self):
        self.assertEqual(status.classify(None), "needs_generation")
        self.assertEqual(
            status.classify({"status": "technical_qa_failed"}),
            "needs_generation",
        )


if __name__ == "__main__":
    unittest.main()
