import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StartProductionContractTests(unittest.TestCase):
    def test_one_click_launcher_exists_and_preserves_order_gate(self):
        text = (ROOT / "START_BLACKINK.bat").read_text(encoding="utf-8")
        self.assertIn("install_blackink_ai.ps1", text)
        self.assertIn("smoke_test_i01.py", text)
        self.assertIn("http://127.0.0.1:8765", text)
        self.assertNotIn("production-state.json", text)

    def test_full_gallery_requires_exact_image_canary_approval(self):
        text = (ROOT / "scripts" / "run_coloring_book.ps1").read_text(encoding="utf-8")
        self.assertIn("ensure_local_ai.ps1", text)
        self.assertIn("sync_engine_for_run.py", text)
        self.assertIn("canary_autopilot_status.py", text)
        self.assertIn("Full 50-page gallery is blocked", text)
        self.assertIn("9/9 exact-image approved", text)
        self.assertNotIn("function Test-Comfy", text)
        self.assertNotIn("/api/tags", text)

    def test_canary_launchers_self_start_local_ai_runtime(self):
        autopilot = (ROOT / "RUN_ENGINE_AUTOPILOT.bat").read_text(encoding="utf-8")
        canary = (ROOT / "RUN_ENGINE_CANARY.bat").read_text(encoding="utf-8")
        for text in (autopilot, canary):
            self.assertIn("ensure_local_ai.ps1", text)
            self.assertIn("powershell -NoProfile -ExecutionPolicy Bypass", text)

    def test_local_ai_runtime_helper_owns_comfy_and_ollama_preflight(self):
        text = (ROOT / "scripts" / "ensure_local_ai.ps1").read_text(encoding="utf-8")
        self.assertIn("/system_stats", text)
        self.assertIn("/api/tags", text)
        self.assertIn("ollama.Source", text)
        self.assertIn("Testing advisory vision reviewer response", text)
        self.assertIn("Starting logged ComfyUI runtime", text)
        self.assertIn("local-runtime-status.json", text)
        self.assertIn('Write-RuntimeStatus "failed"', text)
        self.assertIn('Write-RuntimeStatus "ready"', text)

    def test_local_runtime_diagnostics_are_stage_specific_and_modular(self):
        launcher = (ROOT / "scripts" / "ensure_local_ai.ps1").read_text(encoding="utf-8")
        helpers = (ROOT / "scripts" / "local_runtime_helpers.ps1").read_text(encoding="utf-8")
        self.assertIn("Write-BlackInkRuntimeStatus", launcher)
        self.assertIn('Set-RuntimeStage "comfy-launch"', launcher)
        self.assertIn('Set-RuntimeStage "ollama-launch"', launcher)
        self.assertIn('Set-RuntimeStage "reviewer-smoke-test"', launcher)
        self.assertIn("Start-BlackInkDetachedLocalProcess", launcher)
        self.assertIn(".blackink-tools\\Scripts\\comfy.exe", launcher)
        self.assertIn("--workspace=$comfyWorkspace", launcher)
        self.assertIn("Find-BlackInkComfyWorkspace", helpers)
        self.assertIn("Comfy-Desktop\\ComfyUI-Installs\\Black-Ink Bestiary", helpers)
        self.assertIn("ComfyUI\\main.py", helpers)
        self.assertIn("ComfyUI\\.venv\\Scripts\\python.exe", helpers)
        self.assertIn('"comfy-stop"', launcher)
        self.assertIn('"managed_direct_python"', launcher)
        self.assertIn("Invoke-BlackInkCommand", launcher)
        self.assertIn("System.Diagnostics.ProcessStartInfo", helpers)
        self.assertIn("RedirectStandardError", helpers)
        self.assertIn("Quote-BlackInkArgument", helpers)
        self.assertIn("RedirectStandardOutput", helpers)
        self.assertIn("Get-BlackInkLogTail", helpers)
        self.assertIn("comfy-runtime.stderr.log", launcher)
        self.assertIn("stderr=$stderrTail", launcher)
        self.assertIn("ShellExecute", helpers)
        self.assertIn("Start-Process failed", helpers)

    def test_autopilot_publishes_phase_heartbeat_before_gpu_work(self):
        autopilot = (ROOT / "RUN_ENGINE_AUTOPILOT.bat").read_text(encoding="utf-8")
        heartbeat = (ROOT / "scripts" / "autopilot_heartbeat.py").read_text(encoding="utf-8")
        publisher = (ROOT / "scripts" / "publish_review_previews.py").read_text(encoding="utf-8")

        self.assertIn("autopilot_heartbeat.py generating", autopilot)
        self.assertIn("Publishing pre-GPU heartbeat snapshot", autopilot)
        self.assertIn("autopilot_heartbeat.py sleeping", autopilot)
        self.assertIn("autopilot-heartbeat.json", heartbeat)
        self.assertIn("engine_commit", heartbeat)
        self.assertIn("autopilot-heartbeat.json", publisher)
        self.assertIn('"autopilot": autopilot', publisher)

    def test_runtime_failures_are_published_for_remote_diagnosis(self):
        autopilot = (ROOT / "RUN_ENGINE_AUTOPILOT.bat").read_text(encoding="utf-8")
        canary = (ROOT / "RUN_ENGINE_CANARY.bat").read_text(encoding="utf-8")
        publisher = (ROOT / "scripts" / "publish_review_previews.py").read_text(encoding="utf-8")
        for text in (autopilot, canary):
            self.assertIn("publish_review_previews.py", text)
        self.assertIn("local-runtime-status.json", publisher)
        self.assertIn("local_runtime_failed", publisher)
        self.assertIn('"runtime": runtime', publisher)

    def test_generation_entry_points_run_publishable_engine_preflight(self):
        canary = (ROOT / "RUN_ENGINE_CANARY.bat").read_text(encoding="utf-8")
        autopilot = (ROOT / "RUN_ENGINE_AUTOPILOT.bat").read_text(encoding="utf-8")
        full = (ROOT / "scripts" / "run_coloring_book.ps1").read_text(encoding="utf-8")
        publisher = (ROOT / "scripts" / "publish_review_previews.py").read_text(encoding="utf-8")

        for text in (canary, autopilot, full):
            self.assertIn("engine_preflight.py", text)
            self.assertIn("publish_review_previews.py", text)

        self.assertIn("engine-preflight-status.json", publisher)
        self.assertIn("engine_preflight_failed", publisher)
        self.assertIn('"engine_preflight": engine_preflight', publisher)

    def test_engine_preflight_is_fail_closed_and_autopilot_steps_are_consistent(self):
        preflight = (ROOT / "scripts" / "engine_preflight.py").read_text(encoding="utf-8")
        autopilot = (ROOT / "RUN_ENGINE_AUTOPILOT.bat").read_text(encoding="utf-8")

        self.assertIn("unit-test-launch", preflight)
        self.assertIn("engine-preflight-status.json", preflight)
        self.assertIn('"status": "failed"', preflight)
        for step in range(1, 8):
            self.assertIn(f"[{step}/7]", autopilot)
        self.assertNotIn("[5/6]", autopilot)

    def test_full_gallery_validates_engine_before_starting_local_ai_or_generating(self):
        text = (ROOT / "scripts" / "run_coloring_book.ps1").read_text(encoding="utf-8")
        sync_at = text.index("sync_engine_for_run.py")
        preflight_at = text.index("engine_preflight.py")
        ai_at = text.index("ensure_local_ai.ps1")
        generate_at = text.index("generate_test_gallery.py")
        self.assertLess(sync_at, preflight_at)
        self.assertLess(preflight_at, ai_at)
        self.assertLess(ai_at, generate_at)

    def test_start_doc_names_single_entry_point(self):
        text = (ROOT / "docs" / "START_PRODUCTION.md").read_text(encoding="utf-8")
        self.assertIn("START_BLACKINK.bat", text)
        self.assertIn("APPROVE & LOCK", text)


if __name__ == "__main__":
    unittest.main()
