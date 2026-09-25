import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from defect_taxonomy import classify_text, count_defects, load_taxonomy
from learning_feedback import build_learning_queue, learning_observations
from prompt_load import prompt_load_report
from quality_history import canary_metrics, current_page_records, evaluate_readiness, generation_efficiency, quality_contract_fingerprint


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

    def test_learning_queue_uses_each_refinement_pass_without_double_counting_final(self):
        records = [{
            "page_id": "I-04",
            "candidate": 1,
            "status": "max_refinements_reached",
            "visual_review": {
                "stage": "identity",
                "defects": ["bodybuilder chest and oversized shoulders"],
            },
            "pass_history": [
                {
                    "pass": 0,
                    "review": {
                        "stage": "identity",
                        "defects": ["bodybuilder chest and oversized shoulders"],
                    },
                },
                {
                    "pass": 1,
                    "review": {
                        "stage": "identity",
                        "defects": ["body reads heroically muscular"],
                    },
                },
                {
                    "pass": 2,
                    "review": {
                        "stage": "identity",
                        "defects": ["bodybuilder chest and six-pack abs"],
                    },
                },
            ],
        }]
        observations = learning_observations(records)
        self.assertEqual(len(observations), 4)

        queue = build_learning_queue(records, ROOT)
        item = next(
            row for row in queue
            if row["defect_code"] == "IDENTITY_HEROIC_BULK"
        )
        self.assertEqual(item["evidence_count"], 3)
        self.assertEqual(item["distinct_pages"], 1)
        self.assertEqual(item["priority"], "high")
        self.assertTrue(
            all(
                example["evidence_source"] == "refinement_pass"
                for example in item["examples"]
            )
        )

    def test_learning_queue_surfaces_assistant_notes_as_evidence_text(self):
        records = [{
            "page_id": "I-04",
            "candidate": 2,
            "status": "assistant_rejected",
            "assistant_review": {
                "notes": "Reject: goblin has bodybuilder chest and oversized shoulders",
            },
        }]
        queue = build_learning_queue(records, ROOT)
        item = next(
            row for row in queue
            if row["defect_code"] == "IDENTITY_HEROIC_BULK"
        )
        self.assertIn("bodybuilder chest", item["examples"][0]["evidence_text"][0])

    def test_learning_queue_escalates_cross_family_pattern_to_master_engine(self):
        records = [
            {"page_id": "I-01", "visual_review": {"defects": ["bodybuilder chest"]}},
            {"page_id": "I-04", "visual_review": {"defects": ["heroically muscular"]}},
            {"page_id": "I-08", "visual_review": {"defects": ["muscular superhero mass"]}},
        ]
        queue = build_learning_queue(records, ROOT)
        item = next(
            row for row in queue
            if row["defect_code"] == "IDENTITY_HEROIC_BULK"
        )
        self.assertGreaterEqual(item["distinct_families"], 3)
        self.assertIn("master_engine", item["scope"])
        self.assertIn("multiple monster families", item["master_engine_lesson"])

    def test_learning_queue_scopes_limb_failure_to_master_and_monster(self):
        records = [{
            "page_id": "I-04",
            "visual_review": {
                "stage": "identity",
                "defects": ["goblin has an extra third arm"],
            },
        }]
        queue = build_learning_queue(records, ROOT)
        item = next(row for row in queue if row["defect_code"] == "IDENTITY_LIMB_COUNT")
        self.assertIn("master_engine", item["scope"])
        self.assertIn("monster_family", item["scope"])
        self.assertFalse(item["auto_apply"])
        self.assertIn("exact topology", item["master_engine_lesson"])
        self.assertIn("appendage drift", item["monster_family_lesson"])

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

    def test_reviewer_failure_does_not_masquerade_as_image_technical_failure(self):
        state = {
            "results": [{
                "page_id": "A",
                "candidate": 1,
                "status": "vision_reviewer_failed",
                "error": "reviewer parser failed",
            }]
        }
        metrics = canary_metrics(state, ["A"])
        self.assertEqual(metrics["technical_qa"], 100.0)
        self.assertEqual(metrics["review_pipeline_health"], 0.0)
        self.assertTrue(metrics["rows"][0]["technical_pass"])
        self.assertFalse(metrics["rows"][0]["review_pipeline_pass"])

    def test_generation_efficiency_counts_current_gpu_work_only(self):
        pages = ["A", "B"]
        state = {"results": [
            {
                "page_id": "A",
                "candidate": 1,
                "status": "max_refinements_reached",
                "pass_history": [{}, {}, {}],
                "visual_review": {"stage": "quality", "pass": False},
            },
            {
                "page_id": "B",
                "candidate": 1,
                "status": "ready_for_review",
                "pass_history": [{}],
                "visual_review": {"stage": "quality", "pass": True},
                "assistant_review": {"decision": "approve"},
            },
        ]}
        canary = canary_metrics(state, pages)
        efficiency = generation_efficiency(state, pages, canary)
        self.assertEqual(efficiency["gpu_attempts"], 4)
        self.assertEqual(efficiency["refinement_passes"], 2)
        self.assertEqual(efficiency["pages_at_max_refinements"], 1)
        self.assertEqual(efficiency["avg_gpu_attempts_per_page"], 2.0)
        self.assertEqual(efficiency["semantic_yield_percent"], 50.0)
        self.assertEqual(efficiency["all_gate_yield_percent"], 25.0)

    def test_foundation_requires_current_autopilot_heartbeat_for_full_score(self):
        from unittest.mock import patch
        import quality_history as qh

        fake_series = {
            "pass": True,
            "books_registered": 1,
            "books": [{
                "book_id": "TOME-I",
                "title": "Test",
                "target_pages": 1,
                "recipe_ready": 1,
                "plan_exists": True,
            }],
        }
        fake_active = {"pass": True, "book_id": "TOME-I"}
        fake_scorecard = {
            "contract_version": "test",
            "comparison_authority_paths": [],
            "canary_page_ids": [],
            "required_categories": [
                "foundation_readiness",
                "technical_qa_pass_rate",
                "visual_cleanliness",
                "semantic_accuracy",
                "completeness",
                "print_package_readiness",
                "locked_page_progress",
                "replication_readiness",
            ],
        }
        with patch.object(qh, "load_scorecard", return_value=fake_scorecard), \
             patch.object(qh, "audit_series", return_value=fake_series), \
             patch.object(qh, "audit_active_book", return_value=fake_active), \
             patch.object(qh, "prompt_load_report", return_value={}), \
             patch.object(qh, "print_package_report", return_value={"score": 0}), \
             patch.object(qh, "replication_report", return_value={"score": 0}):
            without = qh.build_quality_snapshot(
                ROOT,
                {"results": []},
                {"status": "ready"},
                {"status": "passed"},
                "abc123",
                autopilot=None,
            )
            with_current = qh.build_quality_snapshot(
                ROOT,
                {"results": []},
                {"status": "ready"},
                {"status": "passed"},
                "abc123",
                autopilot={
                    "status": "ready",
                    "phase": "sleeping",
                    "engine_commit": "abc123",
                },
            )
            with_stale = qh.build_quality_snapshot(
                ROOT,
                {"results": []},
                {"status": "ready"},
                {"status": "passed"},
                "abc123",
                autopilot={
                    "status": "ready",
                    "phase": "sleeping",
                    "engine_commit": "older",
                },
            )

        self.assertEqual(without["metrics"]["foundation_readiness"], 80)
        self.assertEqual(with_current["metrics"]["foundation_readiness"], 100)
        self.assertEqual(with_stale["metrics"]["foundation_readiness"], 80)

    def test_readiness_gate_uses_named_required_categories_and_blockers(self):
        required = [
            "foundation_readiness",
            "technical_qa_pass_rate",
            "visual_cleanliness",
        ]
        metrics = {
            "foundation_readiness": 100,
            "technical_qa_pass_rate": 100,
            "visual_cleanliness": 80,
            "unrelated_bonus_metric": 100,
        }
        report = evaluate_readiness(metrics, required, [])
        self.assertEqual(report["readiness_floor"], 80)
        self.assertEqual(report["weakest_metric"], "visual_cleanliness")
        self.assertFalse(report["automated_100"])

        perfect = {name: 100 for name in required}
        blocked = evaluate_readiness(perfect, required, ["IDENTITY_WRONG_CREATURE"])
        self.assertFalse(blocked["automated_100"])
        self.assertEqual(blocked["readiness_floor"], 100)

        clear = evaluate_readiness(perfect, required, [])
        self.assertTrue(clear["automated_100"])

    def test_missing_required_metric_can_never_claim_100(self):
        report = evaluate_readiness(
            {"foundation_readiness": 100},
            ["foundation_readiness", "technical_qa_pass_rate"],
            [],
        )
        self.assertEqual(report["missing_required_categories"], ["technical_qa_pass_rate"])
        self.assertEqual(report["readiness_floor"], 0)
        self.assertFalse(report["automated_100"])

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

    def test_prompt_load_measures_fixed_canary_generation_and_review_payloads(self):
        report = prompt_load_report(ROOT, ["I-01", "I-04", "I-19"])
        self.assertEqual(report["pages_measured"], 3)
        self.assertEqual(report["errors"], [])
        self.assertGreater(report["generation_chars_avg"], 0)
        self.assertGreater(report["generation_words_avg"], 0)
        self.assertGreater(report["checklist_items_avg"], 0)
        for stage in ("identity", "environment", "action", "quality"):
            self.assertGreater(report["review_chars_avg"][stage], 0)

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
