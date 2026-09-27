import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

import vision_reviewer as vr
import vision_review_prompts as vp


class VisionReviewerTests(unittest.TestCase):
    def test_all_tome_i_pages_have_nonempty_shared_checklist_buckets(self):
        from prompt_builder import build_page_verification_checklist
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        for page in tome["pages"]:
            checklist = build_page_verification_checklist(page)
            self.assertEqual(set(checklist), {"identity", "environment", "action", "quality"})
            for stage, checks in checklist.items():
                self.assertTrue(checks, f"{page['page_id']} missing {stage} checks")

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

    def test_final_quality_gate_explicitly_rejects_decorative_artwork_frames(self):
        prompt = vr.build_review_prompt(self.page)
        self.assertIn("decorative rectangular artwork frame", prompt)
        self.assertIn("inset picture box", prompt)
        self.assertIn("normal blank page margins", prompt)

    def test_prompt_bounds_verdict_size(self):
        prompt = vr.build_review_prompt(self.page)
        lower = prompt.lower()
        self.assertIn("at most 4 defects", lower)
        self.assertIn("3 preserve items", lower)
        self.assertIn("under 80 characters", lower)
        self.assertIn("FINAL COLORING-PAGE GATE", prompt)


    def test_identity_prompt_has_one_defect_wording_rule(self):
        prompt = vr.build_identity_review_prompt(self.page)
        self.assertEqual(
            prompt.count("DEFECT WORDING RULE: defects must describe what is visibly wrong or absent."),
            1,
        )

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
        environment = vr.build_environment_review_prompt(page)
        action = vr.build_action_review_prompt(page)
        self.assertIn("ENVIRONMENT GATES:", environment)
        self.assertIn("Habitat reads as:", environment)
        self.assertIn("Space envelope matches:", environment)
        self.assertIn("ACTION / PHYSICALITY GATES:", action)
        self.assertIn("Scene moment reads as:", action)
        self.assertIn("Physical state reads as:", action)
        self.assertIn("Support/contact is visible and believable:", action)
        self.assertIn("Motion/weight reads correctly:", action)

    def test_scene_pass_requires_concrete_page_specific_evidence(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-10")

        weak_environment = {
            "pass": True,
            "score": 100,
            "defects": [],
            "preserve": ["monster dominates foreground", "stone archway framing", "no decorative frames"],
        }
        strong_environment = {
            "pass": True,
            "score": 96,
            "defects": [],
            "preserve": ["tight spiral dungeon stair", "inner column and curved outer wall"],
        }

        self.assertTrue(vr._stage_pass_evidence_issues(page, "environment", weak_environment))
        self.assertEqual(vr._stage_pass_evidence_issues(page, "environment", strong_environment), [])

    def test_action_pass_requires_contact_and_motion_evidence(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-04")

        weak_action = {
            "pass": True,
            "score": 95,
            "defects": [],
            "preserve": ["small goblin", "narrow corridor"],
        }
        strong_action = {
            "pass": True,
            "score": 95,
            "defects": [],
            "preserve": [
                "kicking foot visibly contacts the lantern",
                "planted foot supports torso while the lantern tips away",
            ],
        }

        self.assertTrue(vr._stage_pass_evidence_issues(page, "action", weak_action))
        self.assertEqual(vr._stage_pass_evidence_issues(page, "action", strong_action), [])

    def test_environment_and_action_prompts_require_pass_evidence(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-10")

        environment = vr.build_environment_review_prompt(page)
        action = vr.build_action_review_prompt(page)

        self.assertIn("PASS EVIDENCE RULE", environment)
        self.assertIn("at least two concrete visible page-specific environment proofs", environment)
        self.assertIn("PASS EVIDENCE RULE", action)
        self.assertIn("at least two concrete visible page-specific action proofs", action)

    def test_review_stages_do_not_leak_into_final_quality_gate(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-10")

        identity = vr.build_identity_review_prompt(page)
        environment = vr.build_environment_review_prompt(page)
        action = vr.build_action_review_prompt(page)
        quality = vr.build_review_prompt(page)

        self.assertIn("Shape-first body geometry reads as:", identity)
        self.assertNotIn("Shape-first body geometry reads as:", quality)

        self.assertIn("Space envelope matches:", environment)
        self.assertNotIn("Scene moment reads as:", environment)

        self.assertIn("Mode-specific contact geometry reads correctly:", action)
        self.assertIn("One clear story beat reads as:", action)
        self.assertIn("Environment participates through:", action)
        self.assertNotIn("Habitat reads as:", action)

        self.assertNotIn("Space envelope matches:", quality)
        self.assertNotIn("Mode-specific contact geometry reads correctly:", quality)
        self.assertNotIn("One clear story beat reads as:", quality)
        self.assertNotIn("Environment participates through:", quality)
        self.assertNotIn("Controlled powered flight allowed by monster data:", quality)

    def test_environment_gate_uses_concrete_geometry_not_generic_question_dump(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-10")
        environment = vr.build_environment_review_prompt(page)
        quality = vr.build_review_prompt(page)

        self.assertIn("Space envelope matches:", environment)
        self.assertIn("Unique landmark is visible:", environment)
        self.assertNotIn("Environment check:", environment)
        self.assertNotIn("Environment check:", quality)

    def test_every_tome_i_page_populates_all_four_review_gates(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        for page in tome["pages"]:
            identity = vr.build_identity_review_prompt(page)
            environment = vr.build_environment_review_prompt(page)
            action = vr.build_action_review_prompt(page)
            quality = vr.build_review_prompt(page)
            self.assertIn("IDENTITY GATES:\n- ", identity, page["page_id"])
            self.assertIn("ENVIRONMENT GATES:\n- ", environment, page["page_id"])
            self.assertIn("ACTION / PHYSICALITY GATES:\n- ", action, page["page_id"])
            self.assertIn("FINAL QUALITY GATES:\n- ", quality, page["page_id"])

    def test_empty_gate_fails_closed(self):
        with patch.object(vp, "_checks", return_value=[]):
            with self.assertRaises(RuntimeError):
                vr.build_identity_review_prompt(self.page)
            with self.assertRaises(RuntimeError):
                vr.build_environment_review_prompt(self.page)
            with self.assertRaises(RuntimeError):
                vr.build_action_review_prompt(self.page)
            with self.assertRaises(RuntimeError):
                vr.build_review_prompt(self.page)

    def test_canonical_scale_and_body_plan_are_hard_gates(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-01")
        prompt = vr.build_identity_review_prompt(page)
        self.assertIn("Canonical scale reads as:", prompt)
        self.assertIn("Canonical body plan reads as:", prompt)
        self.assertIn("adult-human heroic mass", prompt)
        self.assertIn("page-specific prohibited look-alike or known drift", prompt)
        self.assertIn("Reject identity drift:", prompt)

    def test_identity_gate_requires_literal_topology_and_swarm_count_audits(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        centipede = next(item for item in tome["pages"] if item["page_id"] == "I-20")
        rats = next(item for item in tome["pages"] if item["page_id"] == "I-19")

        centipede_prompt = vr.build_identity_review_prompt(centipede)
        rat_prompt = vr.build_identity_review_prompt(rats)

        self.assertIn("COUNTABLE TOPOLOGY AUDIT", centipede_prompt)
        self.assertIn("one-pair-per-segment", centipede_prompt)
        self.assertIn("SWARM COUNT AUDIT", rat_prompt)
        self.assertIn("upper bound as a hard visual limit", rat_prompt)
        self.assertIn("wallpaper density", rat_prompt)

    def test_quality_gate_rejects_page_wide_micro_pattern_load(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        rats = next(item for item in tome["pages"] if item["page_id"] == "I-19")
        prompt = vr.build_review_prompt(rats)
        self.assertIn("COLORING LOAD AUDIT", prompt)
        self.assertIn("repeated grids", prompt)
        self.assertIn("excessive line density", prompt)
        self.assertIn("clearly excessive visible members are an automatic fail", prompt)

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

    def test_all_four_gates_must_pass(self):
        identity = {"pass": True, "score": 96, "defects": [], "preserve": ["small wiry body"]}
        environment = {"pass": True, "score": 95, "defects": [], "preserve": ["stone corridor"]}
        action = {"pass": True, "score": 94, "defects": [], "preserve": ["tripwire crosses floor"]}
        quality = {"pass": True, "score": 92, "defects": [], "preserve": ["broad white regions"]}
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "candidate.png"
            image_path.write_bytes(b"x")
            with patch.object(
                vr,
                "_request",
                side_effect=[
                    {"response": json.dumps(identity)},
                    {"response": json.dumps(environment)},
                    {"response": json.dumps(action)},
                    {"response": json.dumps(quality)},
                ],
            ) as request:
                result = vr.review_image(self.page, image_path, self.config)
        self.assertEqual(result["pass"], quality["pass"])
        self.assertEqual(result["score"], quality["score"])
        self.assertEqual(result["defects"], quality["defects"])
        self.assertEqual(result["preserve"], quality["preserve"])
        self.assertEqual(result["stage"], "quality")
        self.assertEqual(request.call_count, 4)

    def test_environment_failure_stops_before_action_gate(self):
        identity = {"pass": True, "score": 96, "defects": [], "preserve": ["small wiry body"]}
        environment = {"pass": False, "score": 42, "defects": ["spiral stair is not visible"], "preserve": ["stone wall"]}
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "candidate.png"
            image_path.write_bytes(b"x")
            with patch.object(
                vr,
                "_request",
                side_effect=[
                    {"response": json.dumps(identity)},
                    {"response": json.dumps(environment)},
                ],
            ) as request:
                result = vr.review_image(self.page, image_path, self.config)
        self.assertFalse(result["pass"])
        self.assertEqual(result["stage"], "environment")
        self.assertEqual(request.call_count, 2)

    def test_action_failure_stops_before_quality_gate(self):
        identity = {"pass": True, "score": 96, "defects": [], "preserve": ["small wiry body"]}
        environment = {"pass": True, "score": 95, "defects": [], "preserve": ["stone corridor"]}
        action = {"pass": False, "score": 42, "defects": ["tripwire action is not visible"], "preserve": ["stone corridor"]}
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "candidate.png"
            image_path.write_bytes(b"x")
            with patch.object(
                vr,
                "_request",
                side_effect=[
                    {"response": json.dumps(identity)},
                    {"response": json.dumps(environment)},
                    {"response": json.dumps(action)},
                ],
            ) as request:
                result = vr.review_image(self.page, image_path, self.config)
        self.assertFalse(result["pass"])
        self.assertEqual(result["stage"], "action")
        self.assertEqual(request.call_count, 3)

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

    def test_paraphrased_positive_gate_echo_gets_one_consistency_retry(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-16")
        malformed = {
            "pass": False,
            "score": 45,
            "defects": [
                "forelimbs are wings, not separate arms",
                "no dragon or bird anatomy",
            ],
            "preserve": ["four limbs total"],
        }
        corrected = {
            "pass": False,
            "score": 45,
            "defects": ["creature has a humanoid torso and adult-human proportions"],
            "preserve": ["forelimbs are the wings", "no dragon or bird anatomy"],
        }
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "candidate.png"
            image_path.write_bytes(b"x")
            with patch.object(
                vr,
                "_request",
                side_effect=[
                    {"response": json.dumps(malformed)},
                    {"response": json.dumps(corrected)},
                ],
            ) as request:
                result = vr.review_image(page, image_path, self.config)

        self.assertEqual(request.call_count, 2)
        self.assertFalse(result["pass"])
        self.assertEqual(
            result["defects"],
            ["creature has a humanoid torso and adult-human proportions"],
        )

    def test_reviewer_consistency_retry_fails_closed_if_still_self_contradictory(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(item for item in tome["pages"] if item["page_id"] == "I-16")
        malformed = {
            "pass": False,
            "score": 45,
            "defects": ["forelimbs are wings, not separate arms"],
            "preserve": ["four limbs total"],
        }
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "candidate.png"
            image_path.write_bytes(b"x")
            with patch.object(
                vr,
                "_request",
                side_effect=[
                    {"response": json.dumps(malformed)},
                    {"response": json.dumps(malformed)},
                ],
            ):
                with self.assertRaises(vr.VisionReviewError):
                    vr.review_image(page, image_path, self.config)

    def test_negated_failure_is_not_mistaken_for_positive_gate_echo(self):
        prompt = """IDENTITY GATES:
- Identity check: tail is visible
"""
        verdict = {
            "pass": False,
            "score": 45,
            "defects": ["tail not visible"],
            "preserve": ["small wiry body"],
        }
        self.assertEqual(vr._positive_gate_echoes(verdict, prompt), [])

    def test_negative_requirement_echo_is_still_caught_when_polarity_matches(self):
        prompt = """IDENTITY GATES:
- Identity check: no horns or tusks visible
"""
        verdict = {
            "pass": False,
            "score": 45,
            "defects": ["no horns or tusks visible"],
            "preserve": [],
        }
        issues = vr._positive_gate_echoes(verdict, prompt)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["kind"], "positive_gate_echo")

    def test_semantic_overlap_detects_close_positive_paraphrase(self):
        self.assertGreaterEqual(
            vr._semantic_overlap(
                "forelimbs are wings, not separate arms",
                "forelimbs are the wings; no separate arms or hands exist",
            ),
            0.72,
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
