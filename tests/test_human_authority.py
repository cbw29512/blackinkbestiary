import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

STATUS_SCRIPT = ROOT / "scripts" / "canary_autopilot_status.py"
status_spec = importlib.util.spec_from_file_location("human_status", STATUS_SCRIPT)
status = importlib.util.module_from_spec(status_spec)
assert status_spec.loader
status_spec.loader.exec_module(status)

APPLY_SCRIPT = ROOT / "scripts" / "apply_review_decisions.py"
apply_spec = importlib.util.spec_from_file_location("human_apply", APPLY_SCRIPT)
apply = importlib.util.module_from_spec(apply_spec)
assert apply_spec.loader
apply_spec.loader.exec_module(apply)

import sys
sys.path.insert(0, str(ROOT / "art_pipeline"))
from learning_feedback import human_feedback_summary
from quality_history import exact_image_authority_approved


def setup_root(root: Path):
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "web" / "test-gallery").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "review-previews").mkdir(parents=True, exist_ok=True)
    (root / "config" / "quality_scorecard.json").write_text(
        json.dumps({"exact_image_reviewer": "human", "canary_page_ids": ["I-01"]}),
        encoding="utf-8",
    )
    (root / "config" / "defect_taxonomy.json").write_text(
        (ROOT / "config" / "defect_taxonomy.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )


class HumanAuthorityTests(unittest.TestCase):
    def test_old_ai_approval_cannot_satisfy_human_canary_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            setup_root(root)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()[:16]
            base = {
                "page_id": "I-01",
                "candidate": 1,
                "status": "awaiting_exact_image_review",
                "image_path": "test-gallery/I-01-C01.png",
            }
            ai = dict(base, assistant_review={
                "decision": "approve",
                "review_id": f"I-01-C01-H{digest}",
            })
            human = dict(base, assistant_review={
                "decision": "approve",
                "review_id": f"I-01-C01-H{digest}",
                "reviewer": "human",
            })
            self.assertEqual(status.classify(ai, root), "awaiting_review")
            self.assertEqual(status.classify(human, root), "approved")
            self.assertFalse(exact_image_authority_approved(ai, root))
            self.assertTrue(exact_image_authority_approved(human, root))

    def test_nonhuman_decision_is_not_applied_when_human_authority_is_configured(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            setup_root(root)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()[:16]
            review_id = f"I-01-C01-H{digest}"
            state_path = root / "data" / "test-gallery-state.json"
            decisions_path = root / "review-previews" / "decisions.json"
            state_path.write_text(json.dumps({
                "copies_per_page": 1,
                "results": [{
                    "page_id": "I-01",
                    "candidate": 1,
                    "status": "awaiting_exact_image_review",
                    "image_path": "test-gallery/I-01-C01.png",
                }],
                "selections": {},
            }), encoding="utf-8")
            decisions_path.write_text(json.dumps({"reviews": [{
                "review_id": review_id,
                "page_id": "I-01",
                "candidate": 1,
                "decision": "approve",
                "notes": "AI says pass",
            }]}), encoding="utf-8")

            with patch.object(apply, "ROOT", root), patch.object(apply, "STATE", state_path), patch.object(apply, "DECISIONS", decisions_path):
                self.assertEqual(apply.main(), 0)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertNotIn("assistant_review", state["results"][0])
            self.assertEqual(state["selections"], {})

    def test_human_feedback_summary_counts_reasons_and_recurring_defects(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            setup_root(root)
            decisions = {
                "reviews": [
                    {
                        "review_id": "A",
                        "page_id": "I-01",
                        "candidate": 1,
                        "decision": "reject",
                        "reviewer": "human",
                        "stage": "identity",
                        "notes": "bodybuilder chest and oversized shoulders",
                    },
                    {
                        "review_id": "B",
                        "page_id": "I-04",
                        "candidate": 1,
                        "decision": "reject",
                        "reviewer": "human",
                        "stage": "identity",
                        "notes": "heroically muscular bodybuilder proportions",
                    },
                    {
                        "review_id": "C",
                        "page_id": "I-22",
                        "candidate": 1,
                        "decision": "approve",
                        "reviewer": "human",
                        "stage": "quality",
                        "notes": "",
                    },
                    {
                        "review_id": "OLD",
                        "page_id": "I-10",
                        "candidate": 1,
                        "decision": "reject",
                        "stage": "environment",
                        "notes": "old AI decision without reviewer",
                    },
                ]
            }
            (root / "review-previews" / "decisions.json").write_text(
                json.dumps(decisions), encoding="utf-8"
            )
            report = human_feedback_summary(root)
            self.assertEqual(report["total_reviews"], 3)
            self.assertEqual(report["approvals"], 1)
            self.assertEqual(report["rejections"], 2)
            self.assertEqual(report["rejection_stage_counts"]["identity"], 2)
            recurring = {row["defect_code"]: row["count"] for row in report["recurring_defects"]}
            self.assertEqual(recurring["IDENTITY_HEROIC_BULK"], 2)


if __name__ == "__main__":
    unittest.main()
