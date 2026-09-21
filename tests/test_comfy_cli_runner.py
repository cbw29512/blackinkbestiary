import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from comfy_cli_runner import ComfyCli, _parse_machine_output


class _Result:
    returncode = 0
    stdout = '{"ok": true}'
    stderr = ""


class ComfyCliContractTests(unittest.TestCase):
    @patch("comfy_cli_runner.subprocess.run", return_value=_Result())
    def test_json_flag_is_global_before_subcommand(self, run):
        cli = ComfyCli(command="comfy")
        result = cli.run("workflow", "slots", "wf.json", expect_json=True)
        argv = run.call_args.args[0]
        self.assertEqual(argv[:3], ["comfy", "--json", "workflow"])
        self.assertTrue(result["ok"])

    @patch("comfy_cli_runner.subprocess.run", return_value=_Result())
    def test_local_route_is_global_before_subcommand(self, run):
        cli = ComfyCli(command="comfy")
        cli.run("system-stats", expect_json=True, where="local")
        argv = run.call_args.args[0]
        self.assertEqual(argv[:5], ["comfy", "--json", "--where", "local", "system-stats"])

    def test_ndjson_returns_final_envelope(self):
        parsed = _parse_machine_output('{"type":"progress","data":{"value":1}}\n{"ok":true,"data":{"prompt_id":"abc"}}')
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["data"]["prompt_id"], "abc")
        self.assertEqual(len(parsed["_events"]), 2)

    @patch("comfy_cli_runner.subprocess.run", return_value=_Result())
    def test_run_template_json_encodes_params(self, run):
        cli = ComfyCli(command="comfy")
        cli.run_template("example", {"prompt": "a kobold", "seed": 42})
        argv = run.call_args.args[0]
        self.assertIn("--param=prompt=\"a kobold\"", argv)
        self.assertIn("--param=seed=42", argv)

    @patch("comfy_cli_runner.subprocess.run", return_value=_Result())
    def test_plain_commands_do_not_receive_json_flag(self, run):
        cli = ComfyCli(command="comfy")
        cli.run("--version")
        argv = run.call_args.args[0]
        self.assertEqual(argv, ["comfy", "--version"])


if __name__ == "__main__":
    unittest.main()
