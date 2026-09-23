import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from smoke_test_i01 import find_prompt_id, get_current


class SmokeHelpersTests(unittest.TestCase):
    def test_find_prompt_id_nested(self):
        payload = {"data": {"job": {"prompt_id": "abc-123"}}}
        self.assertEqual(find_prompt_id(payload), "abc-123")

    def test_current_i01_is_resolved_before_smoke_generation(self):
        page, _ = get_current()
        self.assertEqual(page["page_id"], "I-01")
        self.assertEqual(page["monster_name"], "Kobold Warrior")
        self.assertEqual(page["habitat"], "Trapped Stone Corridor")
        self.assertEqual(page["_resolved"]["contract_id"], "black-ink-page-v2")


if __name__ == "__main__":
    unittest.main()
