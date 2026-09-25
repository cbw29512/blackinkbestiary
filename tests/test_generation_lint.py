import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from generation_lint import generation_lint_errors
from page_contract import resolve_page_spec
from prompt_builder import build_prompt


class GenerationLintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        cls.pages = [resolve_page_spec(page, ROOT) for page in tome["pages"]]

    def test_every_tome_i_prompt_passes_pre_gpu_lint(self):
        failures = {}
        for page in self.pages:
            errors = generation_lint_errors(page, build_prompt(page, candidate_no=1), ROOT)
            if errors:
                failures[page["page_id"]] = errors
        self.assertEqual(failures, {})

    def test_every_tome_i_prompt_stays_within_target_budget(self):
        standard = json.loads(
            (ROOT / "config" / "coloring_page_standard.json").read_text(encoding="utf-8")
        )
        target = int(standard["generation_prompt_budget"]["target_max_chars"])
        oversized = {}
        for page in self.pages:
            prompt = build_prompt(page, candidate_no=1)
            if len(prompt) > target:
                oversized[page["page_id"]] = len(prompt)
        self.assertEqual(oversized, {})

    def test_identity_recovery_prompts_preserve_required_scene_authority(self):
        canary_ids = {"I-01", "I-08", "I-14", "I-16"}
        failures = {}
        for page in self.pages:
            if page["page_id"] not in canary_ids:
                continue
            prompt = build_prompt(
                page,
                {
                    "stage": "identity",
                    "text": "repeat identity drift",
                    "stagnation_escalation": True,
                    "routing_recommendation": "regenerate",
                },
                candidate_no=1,
            )
            errors = generation_lint_errors(page, prompt, ROOT)
            if errors:
                failures[page["page_id"]] = errors
            self.assertIn("RECOVERY PAGE RECIPE CAPSULE", prompt, page["page_id"])
            self.assertIn("MODEL ENVIRONMENT PRIORITY CAPSULE", prompt, page["page_id"])
            self.assertIn("PAGE RECIPE LOCK — NON-NEGOTIABLE:", prompt, page["page_id"])
        self.assertEqual(failures, {})

    def test_identity_recovery_prompts_stay_within_target_budget(self):
        standard = json.loads(
            (ROOT / "config" / "coloring_page_standard.json").read_text(encoding="utf-8")
        )
        target = int(standard["generation_prompt_budget"]["target_max_chars"])
        oversized = {}
        for page in self.pages:
            prompt = build_prompt(
                page,
                {
                    "stage": "identity",
                    "text": "repeat identity drift",
                    "stagnation_escalation": True,
                    "routing_recommendation": "regenerate",
                },
                candidate_no=1,
            )
            if len(prompt) > target:
                oversized[page["page_id"]] = len(prompt)
        self.assertEqual(oversized, {})

    def test_generation_prompt_priority_order_is_identity_action_environment_style(self):
        for page in self.pages:
            prompt = build_prompt(page, candidate_no=1)
            identity = prompt.index("IDENTITY — HIGHEST PRIORITY:")
            action = prompt.index("ACTION — SECOND PRIORITY:")
            environment = prompt.index("ENVIRONMENT — THIRD PRIORITY:")
            style = prompt.index("BLACK-INK COLORABILITY LOCK:")
            self.assertLess(identity, action, page["page_id"])
            self.assertLess(action, environment, page["page_id"])
            self.assertLess(environment, style, page["page_id"])

    def test_all_gpu_generation_entrypoints_invoke_pre_gpu_lint(self):
        required = (
            "scripts/generate_test_gallery.py",
            "scripts/generate_current_page.py",
            "scripts/generate_golden_page.py",
            "scripts/smoke_test_i01.py",
            "art_pipeline/worker.py",
        )
        missing = []
        for relative in required:
            text = (ROOT / relative).read_text(encoding="utf-8")
            if "assert_generation_ready" not in text:
                missing.append(relative)
        self.assertEqual(missing, [])

    def test_missing_environment_landmark_is_rejected(self):
        page = dict(self.pages[0])
        page["environment_variant"] = dict(page["environment_variant"])
        page["environment_variant"]["landmark"] = "unique impossible lint marker"
        errors = generation_lint_errors(page, build_prompt(self.pages[0], candidate_no=1), ROOT)
        self.assertTrue(any("environment_variant.landmark missing" in item for item in errors))

    def test_exact_include_avoid_conflict_is_rejected(self):
        page = dict(self.pages[0])
        page["must_include"] = list(page.get("must_include") or []) + ["same impossible prop"]
        page["must_avoid"] = list(page.get("must_avoid") or []) + ["same impossible prop"]
        prompt = build_prompt(page, candidate_no=1)
        errors = generation_lint_errors(page, prompt, ROOT)
        self.assertTrue(any("exact requirement conflict" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
