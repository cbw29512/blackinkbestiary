import json
import struct
import tempfile
import unittest
import zlib
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


    def test_edit_prompt_is_preservation_first(self):
        page = {
            "monster_name": "Goblin Minion",
            "habitat": "dungeon pantry",
            "moment": "running away with a stolen ham",
            "identity_rules": [],
            "must_include": ["stolen ham"],
            "must_avoid": ["modern kitchen"],
            "composition": "portrait",
        }
        text = build_edit_prompt(
            page,
            {"text": "make the ham obvious", "quick_tags": ["more white space"]},
        )
        self.assertIn("EDIT THE PROVIDED CURRENT COLORING PAGE", text)
        self.assertIn("Keep every successful part", text)
        self.assertIn("make the ham obvious", text)
        self.assertIn("stolen ham", text)

    def test_every_tome_page_resolves_complete_canonical_spec(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        self.assertEqual(len(tome["pages"]), 50)
        required_visual = {
            "core_identity", "silhouette", "head_features", "body_shape",
            "surface", "signature_gear", "attitude", "must_keep", "must_avoid",
        }
        for page in tome["pages"]:
            self.assertTrue(page.get("monster_spec_id"), page["page_id"])
            spec = load_monster_spec(page)
            self.assertEqual(spec["monster_id"], page["monster_spec_id"])
            self.assertEqual(spec["monster_name"], page["monster_name"])
            self.assertTrue(required_visual.issubset(spec["visual_identity"]))
            self.assertTrue(spec["visual_identity"]["must_keep"])
            self.assertTrue(spec["visual_identity"]["must_avoid"])
            self.assertTrue(spec["accuracy_checks"])
            self.assertTrue(page["must_include"])

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


def _write_grayscale_png(path: Path, value_fn) -> None:
    width, height = 768, 1024
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        rows.extend(value_fn(x, y) for x in range(width))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    raw = (
        b"\\x89PNG\\r\\n\\x1a\\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(raw)


class QATests(unittest.TestCase):
    def test_blank_page_fails_content_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blank.png"
            _write_grayscale_png(path, lambda _x, _y: 255)
            from qa import inspect_candidate
            result = inspect_candidate(path)
            self.assertFalse(result["pass"])
            self.assertIn("near_blank_page", result["reasons"])

    def test_solid_dark_page_fails_content_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dark.png"
            _write_grayscale_png(path, lambda _x, _y: 0)
            from qa import inspect_candidate
            result = inspect_candidate(path)
            self.assertFalse(result["pass"])
            self.assertIn("overly_dark_page", result["reasons"])

    def test_simple_line_art_passes_content_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "line-art.png"
            _write_grayscale_png(
                path,
                lambda x, y: 0 if (x % 64 in {0, 1, 2} or y % 96 in {0, 1}) else 255,
            )
            from qa import inspect_candidate
            result = inspect_candidate(path)
            self.assertTrue(result["content_qa"]["pass"])
            self.assertNotIn("near_blank_page", result["reasons"])

    def test_missing_candidate_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.png"
            from qa import inspect_candidate
            result = inspect_candidate(path)
            self.assertFalse(result["pass"])
            self.assertIn("missing_file", result["reasons"])


if __name__ == "__main__":
    unittest.main()
