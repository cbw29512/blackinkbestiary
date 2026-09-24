import importlib.util
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
        item = {
            "status": "ready_for_review",
            "assistant_review": {"decision": "reject"},
        }
        self.assertEqual(status.classify(item), "needs_generation")

    def test_exact_image_approval_is_terminal_for_canary(self):
        item = {
            "status": "ready_for_review",
            "assistant_review": {"decision": "approve"},
        }
        self.assertEqual(status.classify(item), "approved")

    def test_missing_and_technical_failures_require_generation(self):
        self.assertEqual(status.classify(None), "needs_generation")
        self.assertEqual(
            status.classify({"status": "technical_qa_failed"}),
            "needs_generation",
        )


if __name__ == "__main__":
    unittest.main()
