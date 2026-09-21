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

    def test_start_doc_names_single_entry_point(self):
        text = (ROOT / "docs" / "START_PRODUCTION.md").read_text(encoding="utf-8")
        self.assertIn("START_BLACKINK.bat", text)
        self.assertIn("APPROVE & LOCK", text)


if __name__ == "__main__":
    unittest.main()
