import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from flux2_klein_profile import prepare_distilled_text_to_image


BASE_ID = "base-flux2-klein-subgraph"
DISTILLED_ID = "distilled-flux2-klein-subgraph"


class FakeCli:
    def __init__(self, workflow):
        self.workflow = workflow

    def fetch_template(self, name, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.workflow), encoding="utf-8")
        return {"ok": True, "name": name}


def loader(node_id, node_type, values, model_name=None):
    node = {
        "id": node_id,
        "type": node_type,
        "widgets_values": list(values),
        "inputs": [],
        "properties": {},
    }
    if model_name:
        node["properties"]["models"] = [{"name": model_name, "url": "https://example.invalid/model"}]
    return node


def distilled_definition():
    return {
        "id": DISTILLED_ID,
        "name": "Text to Image (Flux.2 Klein 4B Distilled)",
        "nodes": [
            loader(70, "UNETLoader", ["flux-2-klein-4b.safetensors", "default"], "flux-2-klein-4b.safetensors"),
            loader(71, "CLIPLoader", ["qwen_3_4b.safetensors", "flux2", "default"], "qwen_3_4b.safetensors"),
            loader(72, "VAELoader", ["flux2-vae.safetensors"], "flux2-vae.safetensors"),
            loader(73, "RandomNoise", [999, "randomize"]),
            loader(62, "Flux2Scheduler", [4, 1024, 1024]),
            loader(63, "CFGGuider", [1]),
            loader(66, "EmptyFlux2LatentImage", [1024, 1024, 1]),
            loader(74, "CLIPTextEncode", [""]),
            {
                "id": 68,
                "type": "PrimitiveInt",
                "title": "Width",
                "widgets_values": [1024, "fixed"],
            },
            {
                "id": 69,
                "type": "PrimitiveInt",
                "title": "Height",
                "widgets_values": [1024, "fixed"],
            },
        ],
    }


def template_workflow():
    return {
        "nodes": [
            {"id": 9, "type": "SaveImage", "mode": 0, "widgets_values": ["Flux2-Klein"]},
            {"id": 78, "type": "SaveImage", "mode": 4, "widgets_values": ["Flux2-Klein"]},
            {
                "id": 76,
                "type": "PrimitiveStringMultiline",
                "title": "Prompt",
                "mode": 0,
                "widgets_values": ["demo prompt"],
            },
            {"id": 75, "type": BASE_ID, "mode": 0, "widgets_values": []},
            {"id": 77, "type": DISTILLED_ID, "mode": 4, "widgets_values": []},
        ],
        "links": [
            [154, 75, 0, 9, 0, "IMAGE"],
            [156, 77, 0, 78, 0, "IMAGE"],
        ],
        "definitions": {
            "subgraphs": [
                {
                    "id": BASE_ID,
                    "name": "Text to Image (Flux.2 Klein 4B)",
                    "nodes": [],
                },
                distilled_definition(),
            ]
        },
    }


class Flux2KleinProfileTests(unittest.TestCase):
    def test_prepares_distilled_subgraph_without_promoted_slot_writes(self):
        cli = FakeCli(template_workflow())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prepared.json"
            result = prepare_distilled_text_to_image(
                cli,
                "image_flux2_klein_text_to_image",
                path,
                prompt="kobold in trapped dungeon corridor",
                seed=123,
                model_filename="flux-2-klein-4b-fp8.safetensors",
                clip_filename="qwen_3_4b.safetensors",
                vae_filename="flux2-vae.safetensors",
                width=768,
                height=1024,
            )
            out = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(result["selected_root"], "77")

        top = {str(n["id"]): n for n in out["nodes"]}
        self.assertEqual(top["75"]["mode"], 4)
        self.assertEqual(top["9"]["mode"], 4)
        self.assertEqual(top["77"]["mode"], 0)
        self.assertEqual(top["78"]["mode"], 0)
        self.assertEqual(top["77"]["widgets_values"], [])
        self.assertEqual(top["76"]["widgets_values"][0], "kobold in trapped dungeon corridor")

        definition = next(
            sg for sg in out["definitions"]["subgraphs"]
            if sg["id"] == DISTILLED_ID
        )
        nodes = {n["type"]: n for n in definition["nodes"]}

        self.assertEqual(nodes["UNETLoader"]["widgets_values"][0], "flux-2-klein-4b-fp8.safetensors")
        self.assertEqual(nodes["CLIPLoader"]["widgets_values"][0], "qwen_3_4b.safetensors")
        self.assertEqual(nodes["VAELoader"]["widgets_values"][0], "flux2-vae.safetensors")
        self.assertEqual(nodes["RandomNoise"]["widgets_values"][:2], [123, "fixed"])
        self.assertEqual(nodes["Flux2Scheduler"]["widgets_values"][:3], [4, 768, 1024])
        self.assertEqual(nodes["CFGGuider"]["widgets_values"][0], 1)
        self.assertEqual(nodes["EmptyFlux2LatentImage"]["widgets_values"][:3], [768, 1024, 1])
        self.assertEqual(nodes["CLIPTextEncode"]["widgets_values"][0], "kobold in trapped dungeon corridor")

        primitives = {n.get("title"): n for n in definition["nodes"] if n.get("type") == "PrimitiveInt"}
        self.assertEqual(primitives["Width"]["widgets_values"][0], 768)
        self.assertEqual(primitives["Height"]["widgets_values"][0], 1024)

        self.assertEqual(nodes["UNETLoader"]["properties"]["models"][0]["name"], "flux-2-klein-4b-fp8.safetensors")
        self.assertEqual(nodes["CLIPLoader"]["properties"]["models"][0]["name"], "qwen_3_4b.safetensors")
        self.assertEqual(nodes["VAELoader"]["properties"]["models"][0]["name"], "flux2-vae.safetensors")


if __name__ == "__main__":
    unittest.main()
