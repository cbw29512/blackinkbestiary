import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from smoke_test_i01 import exact_slot, find_prompt_id


class SmokeHelpersTests(unittest.TestCase):
    def test_find_prompt_id_nested(self):
        payload = {"data": {"job": {"prompt_id": "abc-123"}}}
        self.assertEqual(find_prompt_id(payload), "abc-123")

    def test_exact_slot_uses_live_address(self):
        slots = [
            {"address": "57.prompt", "name": "prompt"},
            {"address": "57.seed", "name": "seed"},
        ]
        self.assertEqual(exact_slot(slots, ["prompt", "text"]), "57.prompt")
        self.assertEqual(exact_slot(slots, ["seed"]), "57.seed")

    def test_exact_slot_refuses_ambiguity(self):
        slots = [
            {"address": "1.text", "name": "text"},
            {"address": "2.text", "name": "text"},
        ]
        with self.assertRaises(RuntimeError):
            exact_slot(slots, ["text"])


if __name__ == "__main__":
    unittest.main()
