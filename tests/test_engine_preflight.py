import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "engine_preflight.py"
spec = importlib.util.spec_from_file_location("engine_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(preflight)


class EnginePreflightTests(unittest.TestCase):
    def test_preflight_covers_core_non_gpu_ci_checks(self):
        stages = [stage for stage, _ in preflight.preflight_commands()]
        self.assertEqual(
            stages,
            ["unit-tests", "active-book-audit", "series-audit", "python-compile"],
        )

    def test_run_check_preserves_failure_diagnostics(self):
        fake = SimpleNamespace(returncode=3, stdout="alpha\nbeta\n", stderr="boom\n")
        with patch.object(preflight.subprocess, "run", return_value=fake) as run:
            result = preflight.run_check("unit-tests", ["python", "-m", "unittest"])

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["returncode"], 3)
        self.assertIn("boom", result["output_tail"])
        run.assert_called_once()

    def test_run_check_reports_launch_failure(self):
        with patch.object(preflight.subprocess, "run", side_effect=OSError("missing")):
            result = preflight.run_check("series-audit", ["python", "missing.py"])

        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["returncode"])
        self.assertIn("Could not launch series-audit", result["output_tail"][0])


if __name__ == "__main__":
    unittest.main()
