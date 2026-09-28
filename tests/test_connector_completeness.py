from __future__ import annotations

import json
import unittest
from pathlib import Path

from art_pipeline.connector_completeness import connector_completeness_items
from art_pipeline.environment_prompt import required_object_rules
from art_pipeline.page_contract import resolve_page_spec

ROOT = Path(__file__).resolve().parents[1]


class ConnectorCompletenessTests(unittest.TestCase):
    def test_i01_injects_two_wall_endpoints(self) -> None:
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(p for p in tome["pages"] if p["page_id"] == "I-01")
        proofs = connector_completeness_items(page)
        self.assertEqual(len(proofs), 3)
        self.assertTrue(any("left wall ring" in item for item in proofs))
        self.assertTrue(any("right wall ring" in item for item in proofs))
        self.assertTrue(any("not the creature" in item for item in proofs))

        resolved = resolve_page_spec(page, ROOT)
        for item in proofs:
            self.assertIn(item, resolved["must_include"])
        self.assertIn("tripwire on creature, mouth, or gear", resolved["must_avoid"])
        self.assertIn("tripwire hanging from a torch, sconce, or door handle", resolved["must_avoid"])
        self.assertIn("tripwire diving into a pit or ending inside a hazard", resolved["must_avoid"])

        rules = " ".join(required_object_rules(resolved))
        self.assertNotIn("connect to the triggered hazard", rules.lower())
        self.assertIn("must not dive into the pit", rules)
        self.assertIn("gripped by the creature", rules)

    def test_pages_without_scaffold_stay_unchanged(self) -> None:
        self.assertEqual(connector_completeness_items({"page_id": "X"}), [])


if __name__ == "__main__":
    unittest.main()
