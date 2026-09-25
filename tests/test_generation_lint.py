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
