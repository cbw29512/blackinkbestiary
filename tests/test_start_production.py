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
        self.assertIn("Semantic vision smoke test", text)
        self.assertIn("Starting ComfyUI Desktop", text)
        self.assertIn("local-runtime-status.json", text)
        self.assertIn('Write-RuntimeStatus "failed"', text)
        self.assertIn('Write-RuntimeStatus "ready"', text)

    def test_runtime_failures_are_published_for_remote_diagnosis(self):
        autopilot = (ROOT / "RUN_ENGINE_AUTOPILOT.bat").read_text(encoding="utf-8")
        canary = (ROOT / "RUN_ENGINE_CANARY.bat").read_text(encoding="utf-8")
        publisher = (ROOT / "scripts" / "publish_review_previews.py").read_text(encoding="utf-8")
        for text in (autopilot, canary):
            self.assertIn("publish_review_previews.py", text)
        self.assertIn("local-runtime-status.json", publisher)
        self.assertIn("local_runtime_failed", publisher)
        self.assertIn('"runtime": runtime', publisher)

    def test_start_doc_names_single_entry_point(self):
        text = (ROOT / "docs" / "START_PRODUCTION.md").read_text(encoding="utf-8")
        self.assertIn("START_BLACKINK.bat", text)
        self.assertIn("APPROVE & LOCK", text)


if __name__ == "__main__":
    unittest.main()
