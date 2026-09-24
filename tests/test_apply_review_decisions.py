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

    def test_current_image_hashes_are_indexed_once_per_item(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_file = root / "state.json"
            decisions_file = root / "decisions.json"
            state_file.write_text(json.dumps({
                "results": [
                    {"page_id": "I-01", "candidate": 1, "status": "ready_for_review"},
                    {"page_id": "I-04", "candidate": 1, "status": "ready_for_review"},
                ],
                "selections": {},
            }), encoding="utf-8")
            decisions_file.write_text(json.dumps({
                "reviews": [
                    {"review_id": "old-1", "decision": "reject"},
                    {"review_id": "old-2", "decision": "reject"},
                    {"review_id": "old-3", "decision": "approve"},
                    {"review_id": "old-4", "decision": "approve"},
                ],
            }), encoding="utf-8")

            seen = []
            def fake_review_id(item):
                seen.append((item["page_id"], item["candidate"]))
                return f"current-{item['page_id']}"

            with (
                patch.object(apply, "STATE", state_file),
                patch.object(apply, "DECISIONS", decisions_file),
                patch.object(apply, "review_id_for", side_effect=fake_review_id),
            ):
                self.assertEqual(apply.main(), 0)

            self.assertEqual(
                seen,
                [("I-01", 1), ("I-04", 1)],
            )

    def test_multi_candidate_approvals_do_not_silently_select_last_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_file = root / "state.json"
            decisions_file = root / "decisions.json"
            gallery = root / "web" / "test-gallery"
            gallery.mkdir(parents=True)

            results = []
            reviews = []
            for candidate, payload in ((1, b"one"), (2, b"two")):
                image = gallery / f"I-01-C{candidate:02d}.png"
                image.write_bytes(payload)
                digest = hashlib.sha256(payload).hexdigest()[:16]
                review_id = f"I-01-C{candidate:02d}-H{digest}"
                results.append({
                    "page_id": "I-01",
                    "candidate": candidate,
                    "status": "ready_for_review",
                    "image_path": f"test-gallery/I-01-C{candidate:02d}.png",
                })
                reviews.append({
                    "review_id": review_id,
                    "decision": "approve",
                    "notes": "acceptable",
                })

            state_file.write_text(json.dumps({
                "copies_per_page": 4,
                "results": results,
                "selections": {},
            }), encoding="utf-8")
            decisions_file.write_text(json.dumps({"reviews": reviews}), encoding="utf-8")

            with (
                patch.object(apply, "ROOT", root),
                patch.object(apply, "STATE", state_file),
                patch.object(apply, "DECISIONS", decisions_file),
            ):
                self.assertEqual(apply.main(), 0)

            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["selections"], {})
            self.assertEqual(
                [item["assistant_review"]["decision"] for item in state["results"]],
                ["approve", "approve"],
            )

    def test_select_explicitly_chooses_one_final_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_file = root / "state.json"
            decisions_file = root / "decisions.json"
            image = root / "web" / "test-gallery" / "I-01-C02.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"two")
            digest = hashlib.sha256(b"two").hexdigest()[:16]
            review_id = f"I-01-C02-H{digest}"

            state_file.write_text(json.dumps({
                "copies_per_page": 4,
                "results": [{
                    "page_id": "I-01",
                    "candidate": 2,
                    "status": "ready_for_review",
                    "image_path": "test-gallery/I-01-C02.png",
                }],
                "selections": {},
            }), encoding="utf-8")
            decisions_file.write_text(json.dumps({
                "reviews": [{
                    "review_id": review_id,
                    "decision": "select",
                    "notes": "best final candidate",
                }],
            }), encoding="utf-8")

            with (
                patch.object(apply, "ROOT", root),
                patch.object(apply, "STATE", state_file),
                patch.object(apply, "DECISIONS", decisions_file),
            ):
                self.assertEqual(apply.main(), 0)

            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["results"][0]["assistant_review"]["decision"], "select")
            self.assertEqual(state["selections"]["I-01"], {
                "candidate": 2,
                "source": "assistant_selected",
                "review_id": review_id,
            })

    def test_later_select_supersedes_prior_page_selection_without_rejecting_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_file = root / "state.json"
            decisions_file = root / "decisions.json"
            gallery = root / "web" / "test-gallery"
            gallery.mkdir(parents=True)

            items = []
            reviews = []
            review_ids = []
            for candidate, payload in ((1, b"one"), (2, b"two")):
                image = gallery / f"I-01-C{candidate:02d}.png"
                image.write_bytes(payload)
                digest = hashlib.sha256(payload).hexdigest()[:16]
                review_id = f"I-01-C{candidate:02d}-H{digest}"
                review_ids.append(review_id)
                items.append({
                    "page_id": "I-01",
                    "candidate": candidate,
                    "status": "ready_for_review",
                    "image_path": f"test-gallery/I-01-C{candidate:02d}.png",
                })
                reviews.append({
                    "review_id": review_id,
                    "decision": "select",
                    "notes": f"select candidate {candidate}",
                })

            state_file.write_text(json.dumps({
                "copies_per_page": 4,
                "results": items,
                "selections": {},
            }), encoding="utf-8")
            decisions_file.write_text(json.dumps({"reviews": reviews}), encoding="utf-8")

            with (
                patch.object(apply, "ROOT", root),
                patch.object(apply, "STATE", state_file),
                patch.object(apply, "DECISIONS", decisions_file),
            ):
                self.assertEqual(apply.main(), 0)

            state = json.loads(state_file.read_text(encoding="utf-8"))
            first, second = state["results"]
            self.assertEqual(first["assistant_review"]["decision"], "approve")
            self.assertEqual(
                first["assistant_review"]["selection_superseded_by"],
                review_ids[1],
            )
            self.assertEqual(second["assistant_review"]["decision"], "select")
            self.assertEqual(state["selections"]["I-01"]["candidate"], 2)
            self.assertEqual(state["selections"]["I-01"]["review_id"], review_ids[1])

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
