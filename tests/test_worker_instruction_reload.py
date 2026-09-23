import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))
import worker


class WorkerInstructionReloadTests(unittest.TestCase):
    def test_snapshot_reads_all_authorities_every_time(self):
        required = {
            "universal_monster_contract.json",
            "universal_environment_contract.json",
            "universal_page_contract.json",
            "coloring_page_standard.json",
        }
        first = worker.generation_instruction_snapshot()
        second = worker.generation_instruction_snapshot()
        self.assertEqual(set(first), required)
        self.assertEqual(set(second), required)
        for name in required:
            self.assertIn("content", first[name])
            self.assertIn("mtime_ns", first[name])

    def test_submit_one_reloads_instructions_before_page_context(self):
        events = []
        with patch.object(worker, "generation_instruction_snapshot", side_effect=lambda: events.append("instructions") or {"ok": True}), \
             patch.object(worker, "current_context", side_effect=lambda: events.append("page") or ({}, {})), \
             patch.object(worker.WORKFLOW_FILE, "exists", return_value=False):
            with self.assertRaises(SystemExit):
                worker.submit_one("http://127.0.0.1:8188", None)
        self.assertEqual(events[:2], ["instructions", "page"])


if __name__ == "__main__":
    unittest.main()
