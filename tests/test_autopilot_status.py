from datetime import datetime, timedelta, timezone
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from autopilot_status import STALE_AFTER_SECONDS, activity_health


class AutopilotStatusHealthTests(unittest.TestCase):
    def test_recent_generation_progress_keeps_worker_current(self):
        now = datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc)
        heartbeat = {
            "status": "ready",
            "engine_commit": "abc123",
            "updated_at": (now - timedelta(hours=2)).isoformat(),
        }
        progress = {"updated_at": (now - timedelta(minutes=2)).isoformat()}
        health = activity_health(
            heartbeat,
            progress,
            {},
            {},
            {},
            "abc123",
            now=now,
        )
        self.assertFalse(health["stale"])
        self.assertEqual(health["status"], "ready")
        self.assertEqual(health["last_activity_source"], "generation_progress")
        self.assertTrue(health["engine_current"])

    def test_worker_is_stale_when_all_activity_is_too_old(self):
        now = datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc)
        old = (now - timedelta(seconds=STALE_AFTER_SECONDS + 1)).isoformat()
        health = activity_health(
            {"status": "ready", "engine_commit": "older", "updated_at": old},
            {"updated_at": old},
            {"updated_at": old},
            {},
            {},
            "current",
            now=now,
        )
        self.assertTrue(health["stale"])
        self.assertEqual(health["status"], "stale")
        self.assertFalse(health["engine_current"])

    def test_missing_activity_fails_stale(self):
        health = activity_health({}, {}, {}, {}, {}, "abc123")
        self.assertTrue(health["stale"])
        self.assertIsNone(health["last_activity_at"])
        self.assertIsNone(health["age_seconds"])


if __name__ == "__main__":
    unittest.main()
