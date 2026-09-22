import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from image_edit_profile import prepare_distilled_image_edit
from workflow_adapter import PROMPT_TOKEN, SEED_TOKEN, prepare_workflow, validate_template


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
