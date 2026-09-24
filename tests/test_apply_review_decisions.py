import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply_review_decisions.py"
spec = importlib.util.spec_from_file_location("apply_review_decisions", SCRIPT)
apply = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(apply)


class ApplyReviewDecisionsTests(unittest.TestCase):
    def test_latest_exact_image_decision_wins(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_file = root / "state.json"
            decisions_file = root / "decisions.json"
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()[:16]
            review_id = f"I-01-C01-H{digest}"

            state_file.write_text(json.dumps({
                "results": [{
                    "page_id": "I-01",
                    "candidate": 1,
                    "status": "ready_for_review",
                    "image_path": "test-gallery/I-01-C01.png",
                }],
                "selections": {},
            }), encoding="utf-8")
            decisions_file.write_text(json.dumps({
                "reviews": [
                    {
                        "review_id": review_id,
                        "decision": "reject",
                        "notes": "old rejection",
                    },
                    {
                        "review_id": review_id,
                        "decision": "approve",
                        "notes": "new approval",
                    },
                ],
            }), encoding="utf-8")

            with (
                patch.object(apply, "ROOT", root),
                patch.object(apply, "STATE", state_file),
                patch.object(apply, "DECISIONS", decisions_file),
            ):
                self.assertEqual(apply.main(), 0)

            state = json.loads(state_file.read_text(encoding="utf-8"))
            item = state["results"][0]
            self.assertEqual(item["assistant_review"]["decision"], "approve")
            self.assertEqual(item["assistant_review"]["notes"], "new approval")
            self.assertTrue(image.exists())
            self.assertEqual(state["selections"]["I-01"]["review_id"], review_id)

    def test_reapplying_same_approval_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_file = root / "state.json"
            decisions_file = root / "decisions.json"
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()[:16]
            review_id = f"I-01-C01-H{digest}"
            assistant_review = {
                "review_id": review_id,
                "decision": "approve",
                "notes": "approved",
            }
            state_file.write_text(json.dumps({
                "results": [{
                    "page_id": "I-01",
                    "candidate": 1,
                    "status": "ready_for_review",
                    "image_path": "test-gallery/I-01-C01.png",
                    "assistant_review": assistant_review,
                }],
                "selections": {
                    "I-01": {
                        "candidate": 1,
                        "source": "assistant_review",
                        "review_id": review_id,
                    }
                },
            }), encoding="utf-8")
            decisions_file.write_text(json.dumps({
                "reviews": [{
                    "review_id": review_id,
                    "decision": "approve",
                    "notes": "approved",
                }],
            }), encoding="utf-8")

            before = state_file.read_text(encoding="utf-8")
            with (
                patch.object(apply, "ROOT", root),
                patch.object(apply, "STATE", state_file),
                patch.object(apply, "DECISIONS", decisions_file),
            ):
                self.assertEqual(apply.main(), 0)
            self.assertEqual(state_file.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
