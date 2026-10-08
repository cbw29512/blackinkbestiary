"""Guard review snapshots against historical candidate-state resurrection."""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from review_snapshot_state import latest_candidate_records, reviewable_candidate_records

REVIEWABLE = {"ready_for_review", "awaiting_exact_image_review", "max_refinements_reached"}


class ReviewSnapshotStateTests(unittest.TestCase):
    def test_latest_rejection_suppresses_historical_reviewable_image(self):
        state = {"results": [
            {"page_id": "I-01", "candidate": 1, "status": "ready_for_review"},
            {"page_id": "I-01", "candidate": 1, "status": "assistant_rejected"},
        ]}
        latest = latest_candidate_records(state)
        self.assertEqual(latest[("I-01", 1)]["status"], "assistant_rejected")
        self.assertEqual(reviewable_candidate_records(latest, REVIEWABLE), {})

    def test_later_valid_state_reopens_candidate(self):
        state = {"results": [
            {"page_id": "I-01", "candidate": 1, "status": "failed"},
            {"page_id": "I-01", "candidate": 2, "status": "ready_for_review"},
            {"page_id": "I-01", "candidate": 1, "status": "awaiting_exact_image_review"},
        ]}
        latest = reviewable_candidate_records(latest_candidate_records(state), REVIEWABLE)
        self.assertEqual(set(latest), {("I-01", 1), ("I-01", 2)})

    def test_invalid_candidate_ids_fail_closed(self):
        state = {"results": [
            {"page_id": "I-02", "candidate": "bad", "status": "ready_for_review"},
            {"page_id": "I-03", "candidate": 0, "status": "ready_for_review"},
            {"page_id": "I-04", "candidate": 1, "status": "ready_for_review"},
        ]}
        with self.assertLogs("review_snapshot_state", level="WARNING"):
            latest = latest_candidate_records(state)
        self.assertEqual(set(latest), {("I-04", 1)})

    def test_publisher_main_calls_latest_state_helpers(self):
        publisher = (ROOT / "scripts" / "publish_review_previews.py").read_text(encoding="utf-8")
        tree = ast.parse(publisher)
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        called = {n.func.id for n in ast.walk(main)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertIn("latest_candidate_records", called)
        self.assertIn("reviewable_candidate_records", called)


if __name__ == "__main__":
    unittest.main()
