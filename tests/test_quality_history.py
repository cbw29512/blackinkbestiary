import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from defect_taxonomy import classify_text, count_defects, load_taxonomy
from quality_history import canary_metrics, current_page_records, quality_contract_fingerprint


class QualityHistoryTests(unittest.TestCase):
    def test_defect_taxonomy_classifies_repeated_failure_families(self):
        taxonomy = load_taxonomy(ROOT / "config" / "defect_taxonomy.json")
        codes = classify_text(
            "Reject: goblin is a muscular bodybuilder with horns and orc-like drift.",
            taxonomy,
        )
        self.assertIn("IDENTITY_HEROIC_BULK", codes)
        self.assertIn("IDENTITY_HORNS_TUSKS", codes)

        self.assertIn(
            "IDENTITY_WRONG_CREATURE",
            classify_text("creature has humanoid arms and a primate muzzle", taxonomy),
        )
        self.assertIn(
            "ENVIRONMENT_GENERIC",
            classify_text("no central newel or shaft visible", taxonomy),
        )
        self.assertIn(
            "QUALITY_DENSITY",
            classify_text("excessive repeated rat patterns", taxonomy),
        )

        counts = count_defects([
            {"status": "technical_qa_failed", "error": "safe_margin_too_busy"},
            {"assistant_review": {"notes": "wallpaper-dense swarm with oversized leader"}},
        ], taxonomy)
        self.assertEqual(counts["TECH_SAFE_MARGIN"], 1)
        self.assertEqual(counts["SWARM_WALLPAPER"], 1)
        self.assertEqual(counts["SWARM_OVERSIZED_LEADER"], 1)

    def test_current_page_records_ignore_stale_historical_candidates(self):
        state = {
            "results": [
                {"page_id": "I-01", "candidate": 1, "status": "assistant_rejected", "error": "old failure"},
                {"page_id": "I-01", "candidate": 2, "status": "assistant_rejected", "error": "other old failure"},
                {"page_id": "I-01", "candidate": 1, "status": "ready_for_review", "visual_review": {"pass": True}},
                {"page_id": "I-04", "candidate": 1, "status": "technical_qa_failed"},
            ],
            "selections": {
                "I-01": {"candidate": 1, "source": "assistant_selected"},
            },
        }
        rows = current_page_records(state, ["I-01", "I-04"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["status"], "ready_for_review")
        self.assertEqual(rows[1]["status"], "technical_qa_failed")

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
