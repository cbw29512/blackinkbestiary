import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from local_preflight import local_generation_preflight


class LocalPreflightTests(unittest.TestCase):
    def _root(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "config").mkdir()
        (root / "scripts").mkdir()
        (root / "art_pipeline" / "workflows").mkdir(parents=True)
        (root / "scripts" / "generate_golden_page.py").write_text("# test\n", encoding="utf-8")
        config = {
            "comfy_url": "http://127.0.0.1:8188",
            "templates": {"text_to_image": "text", "modify": "edit"},
            "models": [
                {"folder": "diffusion_models", "filename": "diffusion.safetensors"},
                {"folder": "text_encoders", "filename": "encoder.safetensors"},
                {"folder": "vae", "filename": "vae.safetensors"},
            ],
        }
        (root / "config" / "local_ai_stack.json").write_text(
            json.dumps(config), encoding="utf-8"
        )
        return temp, root

    def test_ready_requires_cli_server_models_templates_and_generator(self):
        temp, root = self._root()
        self.addCleanup(temp.cleanup)

        def fetch(url):
            if url.endswith("/system_stats"):
                return {
                    "system": {"comfyui_version": "test"},
                    "devices": [{"name": "Test GPU"}],
                }
            if "/models/diffusion_models" in url:
                return ["diffusion.safetensors"]
            if "/models/text_encoders" in url:
                return ["encoder.safetensors"]
            if "/models/vae" in url:
                return ["vae.safetensors"]
            return None

        report = local_generation_preflight(
            root,
            fetch_json=fetch,
            cli_finder=lambda: "comfy",
        )
        self.assertTrue(report["ready_for_generation"])
        self.assertEqual(report["required_models_missing"], [])
        self.assertTrue(all(report["checks"].values()))

    def test_missing_model_blocks_generation(self):
        temp, root = self._root()
        self.addCleanup(temp.cleanup)

        def fetch(url):
            if url.endswith("/system_stats"):
                return {"system": {}, "devices": []}
            if "/models/vae" in url:
                return []
            if "/models/" in url:
                if "diffusion_models" in url:
                    return ["diffusion.safetensors"]
                return ["encoder.safetensors"]
            return None

        report = local_generation_preflight(
            root,
            fetch_json=fetch,
            cli_finder=lambda: "comfy",
        )
        self.assertFalse(report["ready_for_generation"])
        self.assertFalse(report["checks"]["required_models"])
        self.assertEqual(report["required_models_missing"], ["vae.safetensors"])

    def test_unreachable_comfyui_blocks_generation(self):
        temp, root = self._root()
        self.addCleanup(temp.cleanup)
        report = local_generation_preflight(
            root,
            fetch_json=lambda _url: None,
            cli_finder=lambda: "comfy",
        )
        self.assertFalse(report["ready_for_generation"])
        self.assertFalse(report["checks"]["comfyui_server"])
        self.assertEqual(len(report["required_models_missing"]), 3)


if __name__ == "__main__":
    unittest.main()
