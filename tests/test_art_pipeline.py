import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from edit_prompt import build_edit_prompt
from prompt_builder import build_prompt, load_monster_spec
from image_edit_profile import prepare_distilled_image_edit
from workflow_adapter import PROMPT_TOKEN, SEED_TOKEN, prepare_workflow, validate_template
from qa import inspect_png


class PromptTests(unittest.TestCase):
    def test_prompt_contains_page_and_style(self):
        page = {
            "page_id": "X-01",
            "order": 1,
            "monster_spec_id": "kobold-warrior",
            "moment": "tripwire triggered",
            "archetype": "trap_scene",
            "must_include": ["pit"],
            "environment_profile_id": "underground.trapped-stone-corridor",
            "environment_variant": {
                "landmark": "open pit beside torch bracket",
                "framing": "tight corridor perspective",
                "interaction": "tripwire triggers the pit",
            },
            "physicality": {
                "mode": "grounded",
                "support": "both feet on the corridor floor",
                "motion": "leaning toward the triggered wire",
            },
        }
        text = build_prompt(page)
        self.assertIn("Kobold Warrior", text)
        self.assertIn("Trapped Stone Corridor", text)
        self.assertIn("large uninterrupted white regions", text)


    def test_edit_prompt_is_preservation_first(self):
        page = {
            "page_id": "X-02",
            "order": 2,
            "monster_spec_id": "goblin-minion",
            "moment": "running away with a stolen ham",
            "archetype": "action_scene",
            "must_include": ["stolen ham"],
            "must_avoid": ["modern kitchen"],
            "environment_profile_id": "underground.rough-stone-pantry",
            "environment_variant": {
                "landmark": "large food shelves",
                "framing": "pantry corner",
                "interaction": "goblin steals food from storage",
            },
            "physicality": {
                "mode": "running",
                "support": "one foot contacts the floor",
                "motion": "forward escape stride",
            },
        }
        text = build_edit_prompt(
            page,
            {"text": "make the ham obvious", "quick_tags": ["more white space"]},
        )
        self.assertIn("EDIT THE PROVIDED CURRENT COLORING PAGE", text)
        self.assertIn("Keep every successful part", text)
        self.assertIn("make the ham obvious", text)
        self.assertIn("stolen ham", text)

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
            "page_id": "X-03",
            "order": 3,
            "monster_spec_id": "kobold-warrior",
            "moment": "waiting",
            "archetype": "lair_scene",
            "environment_profile_id": "underground.limestone-drip-cave",
            "environment_variant": {
                "landmark": "large flowstone shelf",
                "framing": "low cave chamber",
                "interaction": "kobold waits beside the rock shelf",
            },
            "physicality": {
                "mode": "grounded",
                "support": "feet contact the cave floor",
                "motion": "alert waiting stance",
            },
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


    def test_image_edit_preparation_uses_current_image_and_single_input_branch(self):
        workflow = {
            "nodes": [
                {"id": 76, "type": "LoadImage", "widgets_values": ["old.png", "image"]},
                {
                    "id": 75,
                    "type": "single-def",
                    "mode": 0,
                    "inputs": [
                        {"name": "text", "type": "STRING", "link": None},
                        {"name": "image", "type": "IMAGE", "link": 155},
                    ],
                    "widgets_values": ["old-unet", "old-clip", "old-vae", "old prompt", 1],
                },
                {"id": 9, "type": "SaveImage", "mode": 0, "inputs": []},
                {
                    "id": 92,
                    "type": "multi-def",
                    "mode": 4,
                    "inputs": [
                        {"name": "text", "type": "STRING", "link": None},
                        {"name": "image", "type": "IMAGE", "link": 169},
                        {"name": "image_1", "type": "IMAGE", "link": 172},
                    ],
                    "widgets_values": ["x", "y", "z", "multi", 2],
                },
                {"id": 94, "type": "SaveImage", "mode": 4, "inputs": []},
            ],
            "links": [
                [155, 76, 0, 75, 1, "IMAGE"],
                [154, 75, 0, 9, 0, "IMAGE"],
                [171, 92, 0, 94, 0, "IMAGE"],
            ],
            "definitions": {
                "subgraphs": [
                    {
                        "id": "single-def",
                        "name": "Image Edit (Flux.2 Klein 4B Distilled)",
                        "inputs": [
                            {"name": "text", "type": "STRING"},
                            {"name": "image", "type": "IMAGE"},
                        ],
                        "nodes": [
                            {"id": 70, "type": "UNETLoader", "widgets_values": ["old"]},
                            {"id": 71, "type": "CLIPLoader", "widgets_values": ["old"]},
                            {"id": 72, "type": "VAELoader", "widgets_values": ["old"]},
                        ],
                    },
                    {
                        "id": "multi-def",
                        "name": "Image Edit (Flux.2 Klein 4B Distilled) Multi",
                        "inputs": [
                            {"name": "image", "type": "IMAGE"},
                            {"name": "image_1", "type": "IMAGE"},
                        ],
                        "nodes": [],
                    },
                ]
            },
        }

        class FakeCli:
            def fetch_template(self, name, destination):
                destination.write_text(json.dumps(workflow), encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "edit.json"
            result = prepare_distilled_image_edit(
                FakeCli(),
                "template",
                path,
                prompt="keep pose, add ham",
                seed=42,
                input_image="blackink-edits/source.png",
                model_filename="unet.safetensors",
                clip_filename="clip.safetensors",
                vae_filename="vae.safetensors",
            )
            prepared = json.loads(path.read_text(encoding="utf-8"))

        nodes = {node["id"]: node for node in prepared["nodes"]}
        self.assertEqual(nodes[76]["widgets_values"][0], "blackink-edits/source.png")
        self.assertEqual(nodes[75]["widgets_values"][3], "keep pose, add ham")
        self.assertEqual(nodes[75]["widgets_values"][4], 42)
        self.assertEqual(nodes[75]["mode"], 0)
        self.assertEqual(nodes[92]["mode"], 4)
        self.assertEqual(nodes[9]["mode"], 0)
        self.assertEqual(nodes[94]["mode"], 4)
        self.assertEqual(result["root_id"], "75")

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
