import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

import vision_reviewer as vr


class VisionReviewerTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "vision_reviewer": {
                "provider": "ollama",
                "base_url": "http://127.0.0.1:11434",
                "model": "qwen3-vl:4b-instruct",
            }
        }
        self.page = {
            "page_id": "X-01",
            "monster_spec_id": "kobold-warrior",
            "environment_profile_id": "underground.trapped-stone-corridor",
            "moment": "kobold triggers a tripwire",
            "archetype": "trap_scene",
        }

    def test_prompt_bounds_verdict_size(self):
        prompt = vr.build_review_prompt(self.page)
        self.assertIn("at most 4 defects", prompt)
        self.assertIn("at most 3 preserve items", prompt)
        self.assertIn("under 80 characters", prompt)
        self.assertIn("emit the JSON verdict immediately", prompt)

    def test_review_uses_generate_endpoint_with_image(self):
        verdict = {
            "pass": False,
            "score": 20,
            "defects": ["wrong monster identity"],
            "preserve": ["stone corridor"],
        }
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "candidate.png"
            image_path.write_bytes(b"not-a-real-png-but-sufficient-for-base64")
            with patch.object(
                vr,
                "_request",
                return_value={
                    "response": json.dumps(verdict),
                    "done_reason": "stop",
                    "eval_count": 42,
                },
            ) as request:
                result = vr.review_image(self.page, image_path, self.config)

        self.assertEqual(result, verdict)
        url, payload = request.call_args.args[:2]
        self.assertTrue(url.endswith("/api/generate"))
        self.assertIn("prompt", payload)
        self.assertIn("images", payload)
        self.assertEqual(len(payload["images"]), 1)
        self.assertNotIn("messages", payload)
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["think"])

    def test_truncated_non_json_reports_ollama_diagnostics(self):
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "candidate.png"
            image_path.write_bytes(b"x")
            with patch.object(
                vr,
                "_request",
                return_value={
                    "response": '{"pass":false,"score":20,"defects":["wrong identity"',
                    "done_reason": "length",
                    "eval_count": 4096,
                },
            ):
                with self.assertRaises(vr.VisionReviewError) as ctx:
                    vr.review_image(self.page, image_path, self.config)

        message = str(ctx.exception)
        self.assertIn("non-JSON content", message)
        self.assertIn("done_reason=length", message)
        self.assertIn("eval_count=4096", message)

    def test_invalid_verdict_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "candidate.png"
            image_path.write_bytes(b"x")
            with patch.object(
                vr,
                "_request",
                return_value={
                    "response": json.dumps({
                        "pass": "no",
                        "score": 20,
                        "defects": [],
                        "preserve": [],
                    })
                },
            ):
                with self.assertRaises(vr.VisionReviewError):
                    vr.review_image(self.page, image_path, self.config)


if __name__ == "__main__":
    unittest.main()
