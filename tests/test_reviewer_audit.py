import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from reviewer_audit import reviewer_disagreement_report, audit_files


class ReviewerAuditTests(unittest.TestCase):
    def test_only_exact_review_id_matches_count(self):
        manifest = {
            "candidates": [
                {
                    "review_id": "I-04-C01-Haaaa",
                    "page_id": "I-04",
                    "candidate": 1,
                    "source_sha256": "aaaa-full",
                    "visual_review": {"pass": True, "score": 95},
                },
                {
                    "review_id": "I-08-C01-Hbbbb",
                    "page_id": "I-08",
                    "candidate": 1,
                    "source_sha256": "bbbb-full",
                    "visual_review": {"pass": True, "score": 95},
                },
            ]
        }
        decisions = {
            "reviews": [
                {
                    "review_id": "I-04-C01-Hxxxx",
                    "page_id": "I-04",
                    "candidate": 1,
                    "decision": "reject",
                },
                {
                    "review_id": "I-08-C01-Hbbbb",
                    "page_id": "I-08",
                    "candidate": 1,
                    "decision": "reject",
                    "notes": "wrong bugbear anatomy",
                },
            ]
        }
        report = reviewer_disagreement_report(manifest, decisions)
        self.assertEqual(report["exact_image_matches"], 1)
        self.assertEqual(report["local_false_positives"], 1)
        self.assertEqual(report["false_positive_rows"][0]["review_id"], "I-08-C01-Hbbbb")

    def test_false_negative_and_agreement_are_separate(self):
        manifest = {
            "candidates": [
                {"review_id": "A-C01-H1", "visual_review": {"pass": False, "score": 40}},
                {"review_id": "B-C01-H2", "visual_review": {"pass": True, "score": 95}},
            ]
        }
        decisions = {
            "reviews": [
                {"review_id": "A-C01-H1", "decision": "approve"},
                {"review_id": "B-C01-H2", "decision": "select"},
            ]
        }
        report = reviewer_disagreement_report(manifest, decisions)
        self.assertEqual(report["exact_image_matches"], 2)
        self.assertEqual(report["agreements"], 1)
        self.assertEqual(report["local_false_negatives"], 1)
        self.assertEqual(report["local_false_positives"], 0)

    def test_latest_duplicate_decision_wins(self):
        manifest = {
            "candidates": [
                {"review_id": "A-C01-H1", "visual_review": {"pass": True, "score": 95}},
            ]
        }
        decisions = {
            "reviews": [
                {"review_id": "A-C01-H1", "decision": "reject"},
                {"review_id": "A-C01-H1", "decision": "approve"},
            ]
        }
        report = reviewer_disagreement_report(manifest, decisions)
        self.assertEqual(report["agreements"], 1)
        self.assertEqual(report["local_false_positives"], 0)

    def test_audit_files_reads_json_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = root / "manifest.json"
            decisions = root / "decisions.json"
            manifest.write_text(json.dumps({
                "candidates": [
                    {"review_id": "A-C01-H1", "visual_review": {"pass": True, "score": 95}},
                ]
            }), encoding="utf-8")
            decisions.write_text(json.dumps({
                "reviews": [
                    {"review_id": "A-C01-H1", "decision": "reject"},
                ]
            }), encoding="utf-8")
            report = audit_files(manifest, decisions)
            self.assertEqual(report["local_false_positives"], 1)


if __name__ == "__main__":
    unittest.main()
