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
        lower = prompt.lower()
        self.assertIn("at most 4 defects", lower)
        self.assertIn("3 preserve items", lower)
        self.assertIn("under 80 characters", lower)
        self.assertIn("FINAL COLORING-PAGE GATE", prompt)


    def test_identity_prompt_is_fail_closed_and_scale_focused(self):
        prompt = vr.build_identity_review_prompt(self.page)
        lower = prompt.lower()
        self.assertIn("identity and anatomy gate", lower)
        self.assertIn("fail closed", lower)
        self.assertIn("adult-human heroic mass", prompt)
        self.assertIn("Any identity failure must be pass=false and score 49 or lower", prompt)

    def test_goblin_bodybuilder_drift_is_a_hard_identity_gate(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-05")
        prompt = vr.build_identity_review_prompt(page)
        self.assertIn("IDENTITY GATES:", prompt)
        self.assertIn("Fail closed", prompt)
        self.assertIn("bodybuilder-like", prompt)
        self.assertIn("six-pack", prompt)


    def test_habitat_story_and_physicality_are_hard_gates(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-10")
        prompt = vr.build_scene_review_prompt(page)
        self.assertIn("SCENE / PHYSICALITY GATES:", prompt)
        self.assertIn("Habitat reads as:", prompt)
        self.assertIn("Scene moment reads as:", prompt)
        self.assertIn("Physical state reads as:", prompt)
        self.assertIn("Support/contact is visible and believable:", prompt)
        self.assertIn("Motion/weight reads correctly:", prompt)

    def test_review_stages_do_not_leak_into_final_quality_gate(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-10")

        identity = vr.build_identity_review_prompt(page)
        scene = vr.build_scene_review_prompt(page)
        quality = vr.build_review_prompt(page)

        self.assertIn("Shape-first body geometry reads as:", identity)
        self.assertNotIn("Shape-first body geometry reads as:", quality)

        self.assertIn("Mode-specific contact geometry reads correctly:", scene)
        self.assertIn("One clear story beat reads as:", scene)
        self.assertIn("Environment participates through:", scene)

        self.assertNotIn("Mode-specific contact geometry reads correctly:", quality)
        self.assertNotIn("One clear story beat reads as:", quality)
        self.assertNotIn("Environment participates through:", quality)
        self.assertNotIn("Controlled powered flight allowed by monster data:", quality)

    def test_canonical_scale_and_body_plan_are_hard_gates(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-01")
        prompt = vr.build_identity_review_prompt(page)
        self.assertIn("Canonical scale reads as:", prompt)
        self.assertIn("Canonical body plan reads as:", prompt)
        self.assertIn("adult-human heroic mass", prompt)
        self.assertIn("If a bugbear reads gorilla/ape/bodybuilder, fail.", prompt)

    def test_identity_failure_stops_before_quality_review(self):
        verdict = {
            "pass": False,
            "score": 80,
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

        self.assertFalse(result["pass"])
        self.assertEqual(result["score"], 49)
        self.assertEqual(request.call_count, 1)
        url, payload = request.call_args.args[:2]
        self.assertTrue(url.endswith("/api/generate"))
        self.assertIn("identity and anatomy gate", payload["prompt"].lower())
        self.assertEqual(len(payload["images"]), 1)
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["think"])

    def test_all_three_gates_must_pass(self):
        identity = {"pass": True, "score": 96, "defects": [], "preserve": ["small wiry body"]}
        scene = {"pass": True, "score": 94, "defects": [], "preserve": ["tripwire crosses floor"]}
        quality = {"pass": True, "score": 92, "defects": [], "preserve": ["broad white regions"]}
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "candidate.png"
            image_path.write_bytes(b"x")
            with patch.object(
                vr,
                "_request",
                side_effect=[
                    {"response": json.dumps(identity)},
                    {"response": json.dumps(scene)},
                    {"response": json.dumps(quality)},
                ],
            ) as request:
                result = vr.review_image(self.page, image_path, self.config)
        self.assertEqual(result["pass"], quality["pass"])
        self.assertEqual(result["score"], quality["score"])
        self.assertEqual(result["defects"], quality["defects"])
        self.assertEqual(result["preserve"], quality["preserve"])
        self.assertEqual(result["stage"], "quality")
        self.assertEqual(request.call_count, 3)

    def test_scene_failure_stops_before_quality_gate(self):
        identity = {"pass": True, "score": 96, "defects": [], "preserve": ["small wiry body"]}
        scene = {"pass": False, "score": 42, "defects": ["tripwire action is not visible"], "preserve": ["stone corridor"]}
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "candidate.png"
            image_path.write_bytes(b"x")
            with patch.object(
                vr,
                "_request",
                side_effect=[
                    {"response": json.dumps(identity)},
                    {"response": json.dumps(scene)},
                ],
            ) as request:
                result = vr.review_image(self.page, image_path, self.config)
        self.assertFalse(result["pass"])
        self.assertEqual(request.call_count, 2)

    def test_positive_identity_gate_echo_becomes_failure_statement(self):
        prompt = """IDENTITY GATES:
- Identity check: body reads reptilian rather than furry
- Reject identity drift: head becomes round and goblin-like
"""
        verdict = {
            "pass": False,
            "score": 45,
            "defects": [
                "body reads reptilian rather than furry",
                "head becomes round and goblin-like",
            ],
            "preserve": [],
        }
        normalized = vr._normalize_gate_echoes(verdict, prompt)
        self.assertEqual(
            normalized["defects"][0],
            "Required condition not visibly satisfied: body reads reptilian rather than furry",
        )
        self.assertEqual(
            normalized["defects"][1],
            "head becomes round and goblin-like",
        )

    def test_positive_scene_gate_echo_becomes_failure_statement(self):
        prompt = """SCENE / PHYSICALITY GATES:
- Habitat reads as: Cramped Spiral Stair
"""
        verdict = {
            "pass": False,
            "score": 45,
            "defects": ["Habitat reads as: Cramped Spiral Stair"],
            "preserve": [],
        }
        normalized = vr._normalize_gate_echoes(verdict, prompt)
        self.assertEqual(
            normalized["defects"],
            [
                "Required condition not visibly satisfied: "
                "Habitat reads as: Cramped Spiral Stair"
            ],
        )

    def test_positive_interaction_gate_echo_becomes_failure_statement(self):
        prompt = """SCENE / PHYSICALITY GATES:
- Interaction proof is visible: KICKING CONTACT LOCK: foot contacts lantern
- Mode-specific contact geometry reads correctly: one foot planted
"""
        verdict = {
            "pass": False,
            "score": 45,
            "defects": [
                "Interaction proof is visible: KICKING CONTACT LOCK: foot contacts lantern",
                "Mode-specific contact geometry reads correctly: one foot planted",
            ],
            "preserve": [],
        }
        normalized = vr._normalize_gate_echoes(verdict, prompt)
        self.assertTrue(
            all(item.startswith("Required condition not visibly satisfied:") for item in normalized["defects"])
        )

    def test_pass_with_defects_is_forced_to_fail(self):
        verdict = {"pass": True, "score": 95, "defects": ["visible decorative frame"], "preserve": []}
        parsed = vr._parse_verdict({"response": json.dumps(verdict)}, "Quality")
        self.assertFalse(parsed["pass"])
        self.assertEqual(parsed["score"], 49)

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
