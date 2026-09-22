import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from smoke_test_i01 import find_prompt_id


class SmokeHelpersTests(unittest.TestCase):
    def test_find_prompt_id_nested(self):
        payload = {"data": {"job": {"prompt_id": "abc-123"}}}
        self.assertEqual(find_prompt_id(payload), "abc-123")


if __name__ == "__main__":
    unittest.main()
