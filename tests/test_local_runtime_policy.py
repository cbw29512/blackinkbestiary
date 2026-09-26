import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LocalRuntimePolicyTests(unittest.TestCase):
    def test_comfy_launch_is_config_driven_and_logged(self):
        config = json.loads(
            (ROOT / "config" / "local_ai_stack.json").read_text(encoding="utf-8")
        )
        policy = config["production_policy"]
        self.assertEqual(policy["comfy_launch_mode"], "managed_direct_python")
        self.assertIn("--disable-dynamic-vram", policy["comfy_launch_args"])

        launcher = (ROOT / "scripts" / "ensure_local_ai.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("production_policy.comfy_launch_args", launcher)
        self.assertIn("Start-BlackInkDetachedLocalProcess", launcher)
        self.assertIn("data\\comfy-runtime.stdout.log", launcher)
        self.assertIn("data\\comfy-runtime.stderr.log", launcher)

    def test_runtime_logs_stay_local(self):
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("data/comfy-runtime.stdout.log", ignored)
        self.assertIn("data/comfy-runtime.stderr.log", ignored)


if __name__ == "__main__":
    unittest.main()
