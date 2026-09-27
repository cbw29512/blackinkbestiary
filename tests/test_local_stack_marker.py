import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from local_stack_marker import build_marker, verify_marker, write_marker


class LocalStackMarkerTests(unittest.TestCase):
    def make_stack(self, root: Path) -> None:
        config = {
            "workspace": ".blackink-comfy",
            "models": [
                {
                    "folder": "diffusion_models",
                    "filename": "model.safetensors",
                }
            ],
        }
        (root / "config").mkdir(parents=True)
        (root / "config" / "local_ai_stack.json").write_text(
            json.dumps(config),
            encoding="utf-8",
        )
        for relative, payload in {
            ".blackink-tools/Scripts/python.exe": b"python",
            ".blackink-tools/Scripts/comfy.exe": b"comfy",
            ".blackink-comfy/main.py": b"main",
            ".blackink-comfy/models/diffusion_models/model.safetensors": b"model-bytes",
        }.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

    def test_write_then_verify_current_stack(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_stack(root)
            marker = root / "data" / "local-ai-install-marker.json"
            payload = write_marker(root, marker)
            ok, reason = verify_marker(root, marker)
        self.assertTrue(ok, reason)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(len(payload["files"]), 4)

    def test_legacy_nested_layout_remains_readable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_stack(root)
            direct_main = root / ".blackink-comfy" / "main.py"
            nested_main = root / ".blackink-comfy" / "main.py"
            nested_main.parent.mkdir(parents=True, exist_ok=True)
            direct_main.replace(nested_main)
            direct_model = root / ".blackink-comfy" / "models" / "diffusion_models" / "model.safetensors"
            nested_model = root / ".blackink-comfy" / "models" / "diffusion_models" / "model.safetensors"
            nested_model.parent.mkdir(parents=True, exist_ok=True)
            direct_model.replace(nested_model)
            marker_path = root / "data" / "local-ai-install-marker.json"
            write_marker(root, marker_path)
            ok, reason = verify_marker(root, marker_path)
        self.assertTrue(ok, reason)

    def test_config_change_invalidates_marker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_stack(root)
            marker = root / "data" / "local-ai-install-marker.json"
            write_marker(root, marker)
            config_path = root / "config" / "local_ai_stack.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["workspace"] = ".different-workspace"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            ok, reason = verify_marker(root, marker)
        self.assertFalse(ok)
        self.assertIn("configuration changed", reason)

    def test_missing_file_invalidates_marker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_stack(root)
            marker = root / "data" / "local-ai-install-marker.json"
            write_marker(root, marker)
            (root / ".blackink-tools" / "Scripts" / "comfy.exe").unlink()
            ok, reason = verify_marker(root, marker)
        self.assertFalse(ok)
        self.assertIn("missing", reason)

    def test_size_change_invalidates_marker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_stack(root)
            marker = root / "data" / "local-ai-install-marker.json"
            write_marker(root, marker)
            model = root / ".blackink-comfy" / "models" / "diffusion_models" / "model.safetensors"
            model.write_bytes(b"different-size-payload")
            ok, reason = verify_marker(root, marker)
        self.assertFalse(ok)
        self.assertIn("size changed", reason)

    def test_build_marker_fails_closed_when_stack_is_incomplete(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_stack(root)
            (root / ".blackink-comfy" / "main.py").unlink()
            with self.assertRaises(RuntimeError):
                build_marker(root)


if __name__ == "__main__":
    unittest.main()
