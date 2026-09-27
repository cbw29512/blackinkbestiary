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
    def test_validate_workflow_uses_required_workflow_option(self, run):
        cli = ComfyCli(command="comfy")
        cli.validate_workflow(Path("wf.json"))
        argv = run.call_args.args[0]
        self.assertEqual(
            argv,
            ["comfy", "--json", "--where", "local", "workflow", "validate", "--workflow", "wf.json"],
        )

    @patch("comfy_cli_runner.subprocess.run", return_value=_Result())
    def test_run_workflow_uses_run_workflow_wait_contract(self, run):
        cli = ComfyCli(command="comfy")
        cli.run_workflow(Path("wf.json"))
        argv = run.call_args.args[0]
        self.assertIn("run", argv)
        self.assertIn("--workflow", argv)
        self.assertIn("wf.json", argv)
        self.assertIn("--wait", argv)
        self.assertIn("--host", argv)
        self.assertIn("127.0.0.1", argv)
        self.assertIn("--port", argv)
        self.assertIn("8188", argv)
        self.assertIn("--timeout", argv)
        timeout_index = argv.index("--timeout")
        self.assertEqual(argv[timeout_index + 1], "600")
        self.assertEqual(run.call_args.kwargs["timeout"], 630.0)

    @patch("comfy_cli_runner.subprocess.run", return_value=_Result())
    def test_plain_commands_do_not_receive_json_flag(self, run):
        cli = ComfyCli(command="comfy")
        cli.run("--version")
        argv = run.call_args.args[0]
        self.assertEqual(argv, ["comfy", "--version"])


if __name__ == "__main__":
    unittest.main()
