import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EngineLauncherContractTests(unittest.TestCase):
    def test_canary_syncs_before_starting_local_ai(self):
        text = (ROOT / "RUN_ENGINE_CANARY.bat").read_text(encoding="utf-8")
        self.assertLess(
            text.index("scripts\\sync_engine_for_run.py"),
            text.index("scripts\\ensure_local_ai.ps1"),
        )

    def test_autopilot_syncs_before_starting_local_ai(self):
        text = (ROOT / "RUN_ENGINE_AUTOPILOT.bat").read_text(encoding="utf-8")
        self.assertLess(
            text.index("scripts\\sync_engine_for_run.py"),
            text.index("scripts\\ensure_local_ai.ps1"),
        )

    def test_autopilot_always_runs_canary_reconciliation_before_publish(self):
        text = (ROOT / "RUN_ENGINE_AUTOPILOT.bat").read_text(encoding="utf-8")
        self.assertIn(
            "python scripts\\generate_test_gallery.py --canary-failed --copies 1",
            text,
        )
        self.assertLess(
            text.index("scripts\\generate_test_gallery.py"),
            text.index("scripts\\publish_review_previews.py"),
        )
        self.assertNotIn(
            "All current images are waiting for AI review; no GPU regeneration needed.",
            text,
        )


if __name__ == "__main__":
    unittest.main()
