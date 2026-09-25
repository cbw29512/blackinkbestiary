import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from defect_taxonomy import classify_text, count_defects, load_taxonomy
from quality_history import canary_metrics, quality_contract_fingerprint


class QualityHistoryTests(unittest.TestCase):
    def test_defect_taxonomy_classifies_repeated_failure_families(self):
        taxonomy = load_taxonomy(ROOT / "config" / "defect_taxonomy.json")
        codes = classify_text(
            "Reject: goblin is a muscular bodybuilder with horns and orc-like drift.",
            taxonomy,
        )
        self.assertIn("IDENTITY_HEROIC_BULK", codes)
        self.assertIn("IDENTITY_HORNS_TUSKS", codes)

        counts = count_defects([
            {"status": "technical_qa_failed", "error": "safe_margin_too_busy"},
            {"assistant_review": {"notes": "wallpaper-dense swarm with oversized leader"}},
        ], taxonomy)
        self.assertEqual(counts["TECH_SAFE_MARGIN"], 1)
        self.assertEqual(counts["SWARM_WALLPAPER"], 1)
        self.assertEqual(counts["SWARM_OVERSIZED_LEADER"], 1)

    def test_canary_metrics_use_fixed_denominator(self):
        pages = ["A", "B", "C"]
        state = {"results": [
            {
                "page_id": "A", "candidate": 1, "status": "assistant_rejected",
                "visual_review": {"pass": True, "stage": "quality", "score": 95},
                "assistant_review": {"decision": "reject"},
            },
            {
                "page_id": "B", "candidate": 1, "status": "ready_for_review",
                "visual_review": {"pass": True, "stage": "quality", "score": 96},
                "assistant_review": {"decision": "approve"},
            },
            {
                "page_id": "C", "candidate": 1, "status": "technical_qa_failed",
                "error": "safe_margin_too_busy",
            },
        ]}
        report = canary_metrics(state, pages)
        self.assertEqual(report["technical_qa"], 66.7)
        self.assertEqual(report["visual_cleanliness"], 66.7)
        self.assertEqual(report["semantic_accuracy"], 33.3)
        self.assertEqual(report["all_automated_gates"], 33.3)

    def test_quality_contract_fingerprint_changes_with_authority(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "authority.txt").write_text("one", encoding="utf-8")
            cfg = {"comparison_authority_paths": ["authority.txt"]}
            first = quality_contract_fingerprint(root, cfg)
            (root / "authority.txt").write_text("two", encoding="utf-8")
            second = quality_contract_fingerprint(root, cfg)
            self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
