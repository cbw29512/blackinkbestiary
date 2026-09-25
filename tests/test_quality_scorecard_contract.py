import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class QualityScorecardContractTests(unittest.TestCase):
    def setUp(self):
        try:
            self.contract = json.loads(
                (ROOT / "config" / "quality_scorecard.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            self.fail(f"quality scorecard contract could not be loaded: {exc}")

    def test_all_readiness_categories_are_explicit(self):
        self.assertEqual(
            self.contract["required_categories"],
            [
                "foundation_readiness",
                "technical_qa_pass_rate",
                "visual_cleanliness",
                "semantic_accuracy",
                "completeness",
                "print_package_readiness",
                "locked_page_progress",
                "replication_readiness",
            ],
        )

    def test_replication_contract_forbids_engine_name_hacks(self):
        replication = self.contract["replication_readiness_contract"]
        self.assertTrue(replication["creature_specific_data_allowed"])
        self.assertFalse(replication["creature_name_specific_engine_behavior_allowed"])
        requirements = " ".join(replication["score_100_requires"]).lower()
        self.assertIn("ci covers scaffolded future books", requirements)
        self.assertIn("synthetic next-tome test", requirements)

    def test_scoring_implementation_is_part_of_comparison_authority(self):
        self.assertIn(
            "art_pipeline/quality_history.py",
            self.contract["comparison_authority_paths"],
        )
        self.assertIn(
            "readiness floor",
            self.contract["metric_policy"]["readiness_floor_rule"].lower(),
        )

    def test_series_score_is_bounded_by_weakest_book(self):
        policy = self.contract["metric_policy"]
        self.assertIn("weakest registered book", policy["series_score_rule"].lower())
        self.assertIn("every registered book", policy["series_100_rule"].lower())


if __name__ == "__main__":
    unittest.main()
