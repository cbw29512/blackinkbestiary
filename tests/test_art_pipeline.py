import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from prompt_builder import build_prompt, load_monster_spec
from workflow_adapter import PROMPT_TOKEN, SEED_TOKEN, prepare_workflow, validate_template
from qa import inspect_png


class PromptTests(unittest.TestCase):
    def test_prompt_contains_page_and_style(self):
        page = {
            "monster_name": "Kobold Warrior",
            "habitat": "trapped corridor",
            "moment": "tripwire triggered",
            "identity_rules": ["snout", "horn nubs"],
            "must_include": ["pit"],
            "must_avoid": ["gray"],
            "composition": "portrait",
        }
        text = build_prompt(page)
        self.assertIn("Kobold Warrior", text)
        self.assertIn("trapped corridor", text)
        self.assertIn("large uninterrupted white regions", text)

    def test_first_five_tome_pages_resolve_canonical_specs(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        pages = tome["pages"][:5]
        self.assertEqual(
            [page.get("monster_spec_id") for page in pages],
            [
                "kobold-warrior",
                "kobold-shrine-keeper",
                "goblin-minion",
                "goblin-warrior",
                "goblin-boss",
            ],
        )
        for page in pages:
            spec = load_monster_spec(page)
            self.assertEqual(spec["monster_id"], page["monster_spec_id"])
            self.assertTrue(spec["visual_identity"]["must_keep"])
            self.assertTrue(spec["accuracy_checks"])

    def test_canonical_kobold_identity_enters_generation_prompt(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        text = build_prompt(tome["pages"][0])
        self.assertIn("CANONICAL SILHOUETTE", text)
        self.assertIn("long balancing tail", text)
        self.assertIn("goblin-like round head", text)
        self.assertIn("REFERENCE RULE", text)
        self.assertIn("anatomy, silhouette, and identity only", text)

    def test_modify_notes_enter_prompt(self):
        page = {
            "monster_name": "Kobold",
            "habitat": "cave",
            "moment": "waiting",
            "identity_rules": [],
            "must_include": [],
            "must_avoid": [],
            "composition": "portrait",
        }
        text = build_prompt(page, {"text": "simplify walls", "quick_tags": ["more white space"]})
        self.assertIn("simplify walls", text)
        self.assertIn("more white space", text)


class WorkflowTests(unittest.TestCase):
    def test_template_tokens_replace(self):
        template = {"1": {"inputs": {"text": PROMPT_TOKEN, "seed": SEED_TOKEN}}}
        self.assertEqual(validate_template(template), [])
        out = prepare_workflow(template, prompt="hello", seed=123)
        self.assertEqual(out["1"]["inputs"]["text"], "hello")
        self.assertEqual(out["1"]["inputs"]["seed"], 123)

    def test_missing_tokens_rejected(self):
        problems = validate_template({"1": {"inputs": {}}})
        self.assertEqual(len(problems), 2)


class ModelManifestTests(unittest.TestCase):
    def test_v1_model_manifest_is_single_distilled_4b_stack(self):
        manifest_path = ROOT / "art_pipeline" / "model_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        names = [item["filename"] for item in manifest["required_models"]]
        self.assertIn("flux-2-klein-4b-fp8.safetensors", names)
        self.assertIn("qwen_3_4b.safetensors", names)
        self.assertIn("flux2-vae.safetensors", names)
        self.assertFalse(any("9b" in name.lower() for name in names))
        self.assertFalse(any("base-4b" in name.lower() for name in names))
        for item in manifest["required_models"]:
            self.assertTrue(item["url"].startswith("https://huggingface.co/"))


class QATests(unittest.TestCase):
    def test_missing_candidate_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.png"
            from qa import inspect_candidate
            result = inspect_candidate(path)
            self.assertFalse(result["pass"])
            self.assertIn("missing_file", result["reasons"])


if __name__ == "__main__":
    unittest.main()
