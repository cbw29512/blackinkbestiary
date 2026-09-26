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
review = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(review)


def review_id(page_id: str, candidate: int, payload: bytes) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    return f"{page_id}-C{candidate:02d}-H{digest[:16]}"


class ReviewDecisionTests(unittest.TestCase):
    def test_repository_failure_memory_has_valid_schema_and_stages(self):
        payload = json.loads(
            (ROOT / "data" / "review_failure_memory.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload.get("schema_version"), 1)
        allowed = {"identity", "environment", "action", "scene", "quality"}
        self.assertTrue(payload.get("pages"))
        for page_id, rows in payload["pages"].items():
            self.assertTrue(page_id)
            self.assertIsInstance(rows, list)
            for item in rows:
                self.assertIn(str(item.get("stage") or "").lower(), allowed)
                self.assertTrue(str(item.get("notes") or "").strip())

    def test_creature_read_failure_routes_to_identity_not_environment(self):
        item = {"monster_name": "Darkmantle", "visual_review": {"stage": "quality"}}
        review_payload = {
            "decision": "reject",
            "notes": "Reject: does not read as Darkmantle; body is a humanoid winged demon.",
        }
        self.assertEqual(review.classify_rejection_stage(review_payload, item), "identity")

    def test_environment_read_failure_stays_environment(self):
        item = {"monster_name": "Ogre", "visual_review": {"stage": "quality"}}
        review_payload = {
            "decision": "reject",
            "notes": "Reject: anatomy is correct, but the room does not read as a cramped spiral stair.",
        }
        self.assertEqual(review.classify_rejection_stage(review_payload, item), "environment")

    def test_generic_does_not_read_as_phrase_is_not_environment_by_itself(self):
        item = {"monster_name": "Kobold Warrior", "visual_review": {"stage": "identity"}}
        review_payload = {
            "decision": "reject",
            "notes": "Reject: does not read as Kobold Warrior.",
        }
        self.assertEqual(review.classify_rejection_stage(review_payload, item), "identity")

    def test_review_id_binds_exact_image_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-05-C02.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"candidate-version-a")
            item = {
                "page_id": "I-05",
                "candidate": 2,
                "image_path": "test-gallery/I-05-C02.png",
            }
            with patch.object(review, "ROOT", root):
                self.assertEqual(
                    review.review_id_for(item),
                    review_id("I-05", 2, b"candidate-version-a"),
                )

    def test_stale_rejection_does_not_poison_regenerated_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_path = root / "state.json"
            decisions_path = root / "decisions.json"
            image = root / "web" / "test-gallery" / "I-05-C02.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"new-image")
            state_path.write_text(json.dumps({
                "results": [{
                    "page_id": "I-05",
                    "candidate": 2,
                    "seed": 222,
                    "status": "ready_for_review",
                    "image_path": "test-gallery/I-05-C02.png",
                }],
                "selections": {},
            }), encoding="utf-8")
            decisions_path.write_text(json.dumps({
                "reviews": [{
                    "review_id": review_id("I-05", 2, b"old-image"),
                    "decision": "reject",
                    "notes": "old version was too muscular",
                }]
            }), encoding="utf-8")

            with patch.object(review, "ROOT", root), patch.object(review, "STATE", state_path), patch.object(review, "DECISIONS", decisions_path):
                self.assertEqual(review.main(), 0)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["results"][0]["status"], "ready_for_review")
            self.assertTrue(image.exists())

    def test_exact_rejection_marks_retryable_and_deletes_final_preview_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_path = root / "state.json"
            decisions_path = root / "decisions.json"
            image = root / "web" / "test-gallery" / "I-05-C02.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"bad-image")
            state_path.write_text(json.dumps({
                "results": [{
                    "page_id": "I-05",
                    "candidate": 2,
                    "seed": 222,
                    "status": "ready_for_review",
                    "image_path": "test-gallery/I-05-C02.png",
                }],
                "selections": {"I-05": {"candidate": 2}},
            }), encoding="utf-8")
            decisions_path.write_text(json.dumps({
                "reviews": [{
                    "review_id": review_id("I-05", 2, b"bad-image"),
                    "decision": "reject",
                    "notes": "too muscular; reads as a hero portrait",
                }]
            }), encoding="utf-8")

            with patch.object(review, "ROOT", root), patch.object(review, "STATE", state_path), patch.object(review, "DECISIONS", decisions_path):
                self.assertEqual(review.main(), 0)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            item = state["results"][0]
            self.assertEqual(item["status"], "assistant_rejected")
            self.assertEqual(item["assistant_review"]["notes"], "too muscular; reads as a hero portrait")
            self.assertFalse(image.exists())
            self.assertNotIn("I-05", state["selections"])


if __name__ == "__main__":
    unittest.main()
