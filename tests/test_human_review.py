import json
import tempfile
import unittest
from pathlib import Path

from art_pipeline.human_review import append_human_decision, current_canary_items


class HumanReviewTests(unittest.TestCase):
    def make_root(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "config").mkdir()
        (root / "data").mkdir()
        (root / "review-previews").mkdir()
        (root / "web" / "test-gallery").mkdir(parents=True)
        (root / "config" / "quality_scorecard.json").write_text(
            json.dumps({"canary_page_ids": ["I-01"]}), encoding="utf-8"
        )
        state = {
            "results": [{
                "page_id": "I-01",
                "monster_name": "Kobold Warrior",
                "candidate": 1,
                "status": "awaiting_exact_image_review",
                "image_path": "test-gallery/I-01-C01.png",
            }]
        }
        (root / "data" / "test-gallery-state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )
        (root / "web" / "test-gallery" / "I-01-C01.png").write_bytes(b"exact-image")
        return temp, root

    def test_human_reject_requires_reason_and_records_exact_hash(self):
        temp, root = self.make_root()
        self.addCleanup(temp.cleanup)
        item = current_canary_items(root)[0]
        with self.assertRaises(ValueError):
            append_human_decision(root, item, "reject", stage="identity")
        row = append_human_decision(
            root,
            item,
            "reject",
            notes="Creature is adult-human sized rather than a tiny wiry kobold.",
            stage="identity",
        )
        self.assertEqual(row["reviewer"], "human")
        self.assertEqual(row["decision"], "reject")
        self.assertEqual(row["stage"], "identity")
        self.assertTrue(row["review_id"].startswith("I-01-C01-H"))
        payload = json.loads(
            (root / "review-previews" / "decisions.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["reviews"][-1]["reviewer"], "human")

    def test_human_approve_does_not_require_reason(self):
        temp, root = self.make_root()
        self.addCleanup(temp.cleanup)
        item = current_canary_items(root)[0]
        row = append_human_decision(root, item, "approve")
        self.assertEqual(row["decision"], "approve")
        self.assertEqual(row["reviewer"], "human")

    def test_autopilot_waits_instead_of_fake_generation_when_review_is_pending(self):
        text = (Path(__file__).resolve().parents[1] / "RUN_ENGINE_AUTOPILOT.bat").read_text(
            encoding="utf-8"
        )
        self.assertIn('if "!STATE_EXIT!"=="20"', text)
        self.assertIn("WAITING FOR HUMAN REVIEW", text)
        self.assertIn("No GPU generation or duplicate review snapshot publishing", text)
        wait_at = text.index('if "!STATE_EXIT!"=="20"')
        generate_at = text.index("generate_test_gallery.py --canary-failed")
        self.assertLess(wait_at, generate_at)


if __name__ == "__main__":
    unittest.main()
