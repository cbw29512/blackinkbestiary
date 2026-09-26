import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))
import generation_progress as gp


class GenerationProgressTests(unittest.TestCase):
    def test_progress_is_atomic_and_page_specific(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "progress.json"
            with patch.object(gp, "PATH", path):
                payload = gp.write_generation_progress(
                    "I-04", "Goblin Warrior", 1, "rendering",
                    message="ComfyUI is rendering the candidate",
                )
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["page_id"], "I-04")
            self.assertEqual(saved["phase"], "rendering")
            self.assertIn("rendering", saved["message"])


if __name__ == "__main__":
    unittest.main()
