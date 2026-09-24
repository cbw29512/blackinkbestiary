import hashlib
import json
import importlib.util
import tempfile
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
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()[:16]
            item = {
                "page_id": "I-01",
                "candidate": 1,
                "status": "ready_for_review",
                "image_path": "test-gallery/I-01-C01.png",
                "assistant_review": {
                    "decision": "reject",
                    "review_id": f"I-01-C01-H{digest}",
                },
            }
            self.assertEqual(status.classify(item, root), "needs_generation")

    def test_exact_image_approval_is_terminal_for_current_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()[:16]
            item = {
                "page_id": "I-01",
                "candidate": 1,
                "status": "ready_for_review",
                "image_path": "test-gallery/I-01-C01.png",
                "visual_review": {"pass": True},
                "assistant_review": {
                    "decision": "approve",
                    "review_id": f"I-01-C01-H{digest}",
                },
            }
            self.assertEqual(status.classify(item, root), "approved")

    def test_stale_generation_fingerprint_requires_regeneration(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()[:16]
            item = {
                "page_id": "I-01",
                "candidate": 1,
                "status": "ready_for_review",
                "image_path": "test-gallery/I-01-C01.png",
                "generation_fingerprint": "old-engine",
                "assistant_review": {
                    "decision": "approve",
                    "review_id": f"I-01-C01-H{digest}",
                },
            }
            self.assertEqual(
                status.classify(
                    item,
                    root,
                    current_generation_fingerprint="new-engine",
                ),
                "needs_generation",
            )

    def test_stale_reviewer_authority_blocks_old_exact_image_approval(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()[:16]
            item = {
                "page_id": "I-01",
                "candidate": 1,
                "status": "ready_for_review",
                "image_path": "test-gallery/I-01-C01.png",
                "generation_fingerprint": "gen-current",
                "review_fingerprint": "review-old",
                "visual_review": {"pass": True},
                "assistant_review": {
                    "decision": "approve",
                    "review_id": f"I-01-C01-H{digest}",
                },
            }
            self.assertEqual(
                status.classify(
                    item,
                    root,
                    current_generation_fingerprint="gen-current",
                    current_review_fingerprint="review-new",
                ),
                "needs_generation",
            )

    def test_exact_image_approval_also_requires_current_visual_review_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()[:16]
            item = {
                "page_id": "I-01",
                "candidate": 1,
                "status": "max_refinements_reached",
                "image_path": "test-gallery/I-01-C01.png",
                "generation_fingerprint": "gen-current",
                "review_fingerprint": "review-current",
                "visual_review": {"pass": False},
                "assistant_review": {
                    "decision": "approve",
                    "review_id": f"I-01-C01-H{digest}",
                },
            }
            self.assertEqual(
                status.classify(
                    item,
                    root,
                    current_generation_fingerprint="gen-current",
                    current_review_fingerprint="review-current",
                ),
                "awaiting_review",
            )

    def test_stale_approval_does_not_approve_changed_image(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"new-candidate")
            old_digest = hashlib.sha256(b"old-candidate").hexdigest()[:16]
            item = {
                "page_id": "I-01",
                "candidate": 1,
                "status": "ready_for_review",
                "image_path": "test-gallery/I-01-C01.png",
                "assistant_review": {
                    "decision": "approve",
                    "review_id": f"I-01-C01-H{old_digest}",
                },
            }
            self.assertEqual(status.classify(item, root), "awaiting_review")

    def test_canary_page_loader_uses_resolved_generation_authority(self):
        pages = status.load_canary_pages(ROOT)
        resolved = pages["I-01"]

        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        raw = next(page for page in tome["pages"] if page["page_id"] == "I-01")

        resolved_fp = status.page_generation_fingerprint(resolved, ROOT)
        raw_fp = status.page_generation_fingerprint(raw, ROOT)

        self.assertEqual(resolved["monster_name"], "Kobold Warrior")
        self.assertIn("small wiry silhouette is preserved", resolved["identity_rules"])
        self.assertNotEqual(raw_fp, resolved_fp)

        item = {
            "page_id": "I-01",
            "candidate": 1,
            "status": "ready_for_review",
            "generation_fingerprint": resolved_fp,
        }
        self.assertEqual(
            status.classify(
                item,
                ROOT,
                current_generation_fingerprint=resolved_fp,
            ),
            "awaiting_review",
        )

    def test_missing_and_technical_failures_require_generation(self):
        self.assertEqual(status.classify(None), "needs_generation")
        self.assertEqual(
            status.classify({"status": "technical_qa_failed"}),
            "needs_generation",
        )


if __name__ == "__main__":
    unittest.main()
