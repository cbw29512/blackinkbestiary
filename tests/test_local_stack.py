import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LocalStackConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "config" / "local_ai_stack.json").read_text(encoding="utf-8"))

    def test_pins_expected_cli_and_model(self):
        self.assertEqual(self.config["comfy_cli_version"], "1.20.0")
        self.assertEqual(self.config["model"]["variant"], "4B distilled FP8")

    def test_exactly_three_core_model_files(self):
        models = self.config["models"]
        self.assertEqual(len(models), 3)
        names = {item["filename"] for item in models}
        self.assertEqual(names, {
            "flux-2-klein-4b-fp8.safetensors",
            "qwen_3_4b.safetensors",
            "flux2-vae.safetensors",
        })
        for item in models:
            self.assertEqual(len(item["sha256"]), 64)
            self.assertTrue(item["relative_path"].startswith("models/"))

    def test_official_template_names_are_locked(self):
        self.assertEqual(
            self.config["templates"]["text_to_image"],
            "image_flux2_klein_text_to_image",
        )
        self.assertEqual(
            self.config["templates"]["modify"],
            "image_flux2_klein_image_edit_4b_distilled",
        )

    def test_production_policy_stays_narrow(self):
        policy = self.config["production_policy"]
        self.assertFalse(policy["custom_nodes"])
        self.assertFalse(policy["auto_update_comfyui"])
        self.assertTrue(policy["ordered_pages"])
        self.assertTrue(policy["current_page_only"])


if __name__ == "__main__":
    unittest.main()
