import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from flux2_klein_profile import (
    activate_branch,
    build_distilled_overrides,
    prompt_slot,
    select_distilled_branch,
)


class Flux2KleinProfileTests(unittest.TestCase):
    def sample_slots(self):
        return [
            {"address": "76.value", "name": "value", "node_type": "PrimitiveStringMultiline", "current_value": "demo"},
            {"address": "75.unet_name", "name": "unet_name", "current_value": "flux-2-klein-base-4b.safetensors"},
            {"address": "75.noise_seed", "name": "noise_seed", "current_value": 0},
            {"address": "75.value", "name": "value", "current_value": 1024},
            {"address": "75.value_1", "name": "value_1", "current_value": 1024},
            {"address": "75/62.steps", "name": "steps", "current_value": 20},
            {"address": "75/63.cfg", "name": "cfg", "current_value": 5},
            {"address": "77.unet_name", "name": "unet_name", "current_value": "flux-2-klein-4b.safetensors"},
            {"address": "77.noise_seed", "name": "noise_seed", "current_value": 99},
            {"address": "77.value", "name": "value", "current_value": 1024},
            {"address": "77.value_1", "name": "value_1", "current_value": 1024},
            {"address": "77/62.steps", "name": "steps", "current_value": 4},
            {"address": "77/63.cfg", "name": "cfg", "current_value": 1},
        ]

    def test_selects_distilled_four_step_branch(self):
        root, roots = select_distilled_branch(self.sample_slots())
        self.assertEqual(root, "77")
        self.assertEqual(roots, ["75", "77"])
        self.assertEqual(prompt_slot(self.sample_slots()), "76.value")

    def test_builds_exact_distilled_overrides(self):
        slots = self.sample_slots()
        root, _ = select_distilled_branch(slots)
        out = build_distilled_overrides(
            slots,
            root,
            prompt="kobold",
            seed=123,
            model_filename="flux-2-klein-4b-fp8.safetensors",
            width=768,
            height=1024,
        )
        self.assertEqual(out["76.value"], "kobold")
        self.assertEqual(out["77.unet_name"], "flux-2-klein-4b-fp8.safetensors")
        self.assertEqual(out["77.noise_seed"], 123)
        self.assertEqual(out["77.value"], 768)
        self.assertEqual(out["77.value_1"], 1024)
        self.assertEqual(out["77/62.steps"], 4)
        self.assertEqual(out["77/63.cfg"], 1)

    def test_activates_only_distilled_branch_and_its_save_node(self):
        workflow = {
            "nodes": [
                {"id": 9, "type": "SaveImage", "mode": 0},
                {"id": 78, "type": "SaveImage", "mode": 4},
                {"id": 75, "type": "base-subgraph", "mode": 0},
                {"id": 77, "type": "distilled-subgraph", "mode": 4},
            ],
            "links": [
                [154, 75, 0, 9, 0, "IMAGE"],
                [156, 77, 0, 78, 0, "IMAGE"],
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wf.json"
            path.write_text(json.dumps(workflow), encoding="utf-8")
            activate_branch(path, "77", ["75", "77"])
            out = json.loads(path.read_text(encoding="utf-8"))

        modes = {str(n["id"]): n["mode"] for n in out["nodes"]}
        self.assertEqual(modes["75"], 4)
        self.assertEqual(modes["9"], 4)
        self.assertEqual(modes["77"], 0)
        self.assertEqual(modes["78"], 0)


if __name__ == "__main__":
    unittest.main()
