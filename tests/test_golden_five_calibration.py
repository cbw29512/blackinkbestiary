import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from calibration_gate import (
    calibration_case,
    calibration_report,
    load_calibration_config,
    validate_calibration,
)
from calibration_service import public_calibration_state
from calibration_state import load_calibration_state, set_calibration_generation_error


class GoldenFiveCalibrationTests(unittest.TestCase):
    def test_calibration_contract_is_valid(self):
        self.assertEqual(validate_calibration(ROOT), [])

    def test_golden_five_are_deliberately_different_tome_i_pages(self):
        config = load_calibration_config()
        ids = [case["page_id"] for case in config["cases"]]
        self.assertEqual(ids, ["I-01", "I-24", "I-27", "I-38", "I-40"])
        self.assertEqual(len(set(ids)), 5)
        self.assertTrue(all(case["stress_test"] for case in config["cases"]))

    def test_all_quality_dimensions_are_required(self):
        config = load_calibration_config()
        quality = json.loads(
            (ROOT / "config" / "quality_rules.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            set(config["required_review_dimensions"]),
            set(quality["review_dimensions"]),
        )

    def test_initial_calibration_does_not_claim_production_readiness(self):
        report = calibration_report(ROOT)
        self.assertTrue(report["pass"])
        self.assertEqual(report["approved"], 0)
        self.assertEqual(report["required"], 5)
        self.assertFalse(report["production_calibrated"])

    def test_ankheg_calibration_forbids_airborne_freeze_frame(self):
        case = calibration_case("I-38")
        rule = case["special_rule"].lower()
        self.assertIn("lower body visibly supported", rule)
        self.assertIn("never depict a midair", rule)

    def test_generation_error_is_exposed_and_can_be_cleared(self):
        state_path = ROOT / "data" / "golden-five-state.json"
        original = state_path.read_text(encoding="utf-8")
        try:
            set_calibration_generation_error(ROOT, "I-01", "template fetch failed")
            payload = public_calibration_state(ROOT)
            page = next(item for item in payload["pages"] if item["page_id"] == "I-01")
            self.assertEqual(page["generation_error"]["message"], "template fetch failed")

            set_calibration_generation_error(ROOT, "I-01", None)
            state = load_calibration_state(ROOT)
            self.assertNotIn("generation_error", state["pages"]["I-01"])
        finally:
            state_path.write_text(original, encoding="utf-8")
    def test_studio_calibration_payload_exposes_five_reviewable_pages(self):
        payload = public_calibration_state(ROOT)
        self.assertEqual(len(payload["pages"]), 5)
        self.assertEqual(
            len(payload["required_review_dimensions"]),
            6,
        )
        self.assertFalse(payload["report"]["production_calibrated"])
        self.assertFalse(payload["worker"]["running"])

    def test_studio_loads_split_calibration_scripts(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("golden-five-view.js", html)
        self.assertIn("golden-five.js", html)
        self.assertLess(
            html.index("golden-five-view.js"),
            html.index("golden-five.js"),
        )

    def test_tome_i_clean_rebuild_starts_queued(self):
        state = json.loads(
            (ROOT / "data" / "production-state.json").read_text(encoding="utf-8")
        )
        first = state["pages"]["I-01"]
        self.assertEqual(state["current_page_id"], "I-01")
        self.assertEqual(first["status"], "queued")
        self.assertIsNone(first["current_candidate"])


if __name__ == "__main__":
    unittest.main()
