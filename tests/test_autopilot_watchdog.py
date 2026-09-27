from datetime import datetime, timedelta, timezone
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from autopilot_watchdog import build_health


class AutopilotWatchdogTests(unittest.TestCase):
    def _write(self, root: Path, relative: str, updated_at: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"updated_at": updated_at}), encoding="utf-8")

    def test_missing_activity_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            report = build_health(Path(td))
        self.assertTrue(report["stale"])
        self.assertEqual(report["status"], "stale")
        self.assertIsNone(report["last_activity_at"])

    def test_recent_generation_progress_keeps_worker_healthy(self):
        now = datetime(2026, 9, 27, 15, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write(
                root,
                "data/generation-progress.json",
                (now - timedelta(minutes=8)).isoformat(),
            )
            self._write(
                root,
                "data/autopilot-heartbeat.json",
                (now - timedelta(hours=2)).isoformat(),
            )
            report = build_health(root, max_age_minutes=45, now=now)
        self.assertFalse(report["stale"])
        self.assertEqual(report["last_activity_source"], "generation_progress")

    def test_all_old_activity_is_stale(self):
        now = datetime(2026, 9, 27, 15, 0, tzinfo=timezone.utc)
        old = (now - timedelta(minutes=46)).isoformat()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for relative in (
                "data/autopilot-heartbeat.json",
                "data/generation-progress.json",
                "data/test-gallery-state.json",
                "data/local-runtime-status.json",
                "data/engine-preflight-status.json",
            ):
                self._write(root, relative, old)
            report = build_health(root, max_age_minutes=45, now=now)
        self.assertTrue(report["stale"])
        self.assertGreater(report["age_seconds"], 45 * 60)

    def test_future_clock_skew_does_not_false_fail(self):
        now = datetime(2026, 9, 27, 15, 0, tzinfo=timezone.utc)
        future = (now + timedelta(minutes=2)).isoformat()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write(root, "data/autopilot-heartbeat.json", future)
            report = build_health(root, max_age_minutes=45, now=now)
        self.assertFalse(report["stale"])
        self.assertEqual(report["age_seconds"], 0)


if __name__ == "__main__":
    unittest.main()
