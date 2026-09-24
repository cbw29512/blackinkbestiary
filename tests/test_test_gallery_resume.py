import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_test_gallery.py"
spec = importlib.util.spec_from_file_location("generate_test_gallery", SCRIPT)
gallery = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(gallery)


class TestGalleryResumeTests(unittest.TestCase):
    def test_clear_selection_for_candidate_removes_only_matching_candidate(self):
        state = {
            "selections": {
                "I-01": {
                    "candidate": 2,
                    "source": "assistant_selected",
                    "review_id": "I-01-C02-Habc",
                }
            }
        }
        self.assertFalse(gallery.clear_selection_for_candidate(state, "I-01", 1))
        self.assertIn("I-01", state["selections"])
        self.assertTrue(gallery.clear_selection_for_candidate(state, "I-01", 2))
        self.assertNotIn("I-01", state["selections"])

    def test_existing_success_is_skipped(self):
        prior = {"status": "ready_for_review"}
        self.assertTrue(gallery.should_skip_candidate(prior, False))
        self.assertTrue(gallery.should_skip_candidate(prior, True))

    def test_failed_candidate_can_be_retried(self):
        prior = {"status": "technical_qa_failed"}
        self.assertTrue(gallery.should_skip_candidate(prior, False))
        self.assertFalse(gallery.should_skip_candidate(prior, True))


    def test_exhausted_candidate_retries_when_current_reviewer_just_failed_it(self):
        prior = {"status": "max_refinements_reached"}
        self.assertTrue(
            gallery.should_skip_candidate(
                prior,
                True,
                retry_max_refinements=False,
            )
        )
        self.assertFalse(
            gallery.should_skip_candidate(
                prior,
                True,
                retry_max_refinements=True,
            )
        )

    def test_current_exact_assistant_approval_is_terminal_even_if_local_review_failed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"approved-image")
            digest = hashlib.sha256(b"approved-image").hexdigest()[:16]
            prior = {
                "page_id": "I-01",
                "candidate": 1,
                "status": "max_refinements_reached",
                "image_path": "test-gallery/I-01-C01.png",
                "generation_fingerprint": "gen-current",
                "review_fingerprint": "review-old",
                "visual_review": {"pass": False, "stage": "quality"},
                "assistant_review": {
                    "decision": "approve",
                    "review_id": f"I-01-C01-H{digest}",
                },
            }
            with patch.object(gallery, "ROOT", root):
                self.assertTrue(
                    gallery.exact_assistant_approval_is_current(
                        prior,
                        "gen-current",
                    )
                )
                self.assertFalse(
                    gallery.exact_assistant_approval_is_current(
                        prior,
                        "gen-new",
                    )
                )

    def test_non_identity_assistant_rejection_reuses_exact_image_for_targeted_edit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-10-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"candidate")
            prior = {
                "page_id": "I-10",
                "candidate": 1,
                "status": "assistant_rejected",
                "image_path": "test-gallery/I-10-C01.png",
                "assistant_review": {
                    "decision": "reject",
                    "stage": "environment",
                    "notes": "spiral stair is not visible",
                },
            }
            with patch.object(gallery, "ROOT", root):
                source, verdict = gallery.assistant_repair_plan(prior)

            self.assertEqual(source, image)
            self.assertEqual(verdict["stage"], "environment")
            self.assertIn("spiral stair is not visible", verdict["defects"])

    def test_identity_assistant_rejection_never_reuses_bad_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-14-C01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"bad-body-plan")
            prior = {
                "page_id": "I-14",
                "candidate": 1,
                "status": "assistant_rejected",
                "image_path": "test-gallery/I-14-C01.png",
                "assistant_review": {
                    "decision": "reject",
                    "stage": "identity",
                    "notes": "wrong body plan",
                },
            }
            with patch.object(gallery, "ROOT", root):
                source, verdict = gallery.assistant_repair_plan(prior)

            self.assertIsNone(source)
            self.assertIsNone(verdict)

    def test_assistant_rejected_candidate_can_be_retried(self):
        prior = {"status": "assistant_rejected"}
        self.assertTrue(gallery.should_skip_candidate(prior, False))
        self.assertFalse(gallery.should_skip_candidate(prior, True))

    def test_stale_generation_authority_forces_canary_rerun(self):
        prior = {
            "status": "ready_for_review",
            "generation_fingerprint": "old",
        }
        self.assertTrue(gallery.generation_authority_stale(prior, "new"))
        self.assertFalse(
            gallery.should_skip_candidate(
                prior,
                True,
                force_rerun=gallery.generation_authority_stale(prior, "new"),
                retry_max_refinements=False,
            )
        )

    def test_current_generation_authority_keeps_reviewable_candidate_skipped(self):
        prior = {
            "status": "ready_for_review",
            "generation_fingerprint": "same",
        }
        self.assertFalse(gallery.generation_authority_stale(prior, "same"))
        self.assertTrue(
            gallery.should_skip_candidate(
                prior,
                True,
                force_rerun=gallery.generation_authority_stale(prior, "same"),
                retry_max_refinements=False,
            )
        )

    def test_review_authority_staleness_is_independent_from_generation(self):
        prior = {
            "status": "ready_for_review",
            "generation_fingerprint": "pixels-same",
            "review_fingerprint": "review-old",
        }
        self.assertFalse(
            gallery.generation_authority_stale(prior, "pixels-same")
        )
        self.assertTrue(
            gallery.review_authority_stale(prior, "review-new")
        )

    def test_existing_candidate_path_requires_real_current_png(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "web" / "test-gallery" / "I-01-C01.png"
            image.parent.mkdir(parents=True)
            item = {"image_path": "test-gallery/I-01-C01.png"}
            with patch.object(gallery, "ROOT", root):
                self.assertIsNone(gallery.existing_candidate_path(item))
                image.write_bytes(b"png")
                self.assertEqual(gallery.existing_candidate_path(item), image)

    def test_canary_force_reruns_existing_candidate(self):
        prior = {"status": "ready_for_review"}
        self.assertFalse(gallery.should_skip_candidate(prior, False, force_rerun=True))
        self.assertEqual(
            gallery.CANARY_PAGE_IDS,
            ("I-01", "I-04", "I-08", "I-10", "I-14", "I-16", "I-19", "I-20", "I-22"),
        )

    def test_canary_summary_reports_each_required_page(self):
        state = {"results": []}
        for page_id in gallery.CANARY_PAGE_IDS:
            state["results"].append({
                "page_id": page_id,
                "candidate": 1,
                "status": "ready_for_review",
                "visual_review": {"score": 93, "defects": []},
            })
        summary = gallery.canary_summary(state)
        self.assertEqual(summary["ready"], len(gallery.CANARY_PAGE_IDS))
        self.assertEqual(summary["total"], len(gallery.CANARY_PAGE_IDS))
        self.assertEqual([row["page_id"] for row in summary["rows"]], list(gallery.CANARY_PAGE_IDS))

    def test_refinement_uses_latest_image_even_when_score_does_not_improve(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "web" / "candidates").mkdir(parents=True)
            initial = root / "initial.png"
            initial.write_bytes(b"x")
            seen_sources = []

            def fake_prepare_edit(cli, client, config, page, seed, candidate_no, source, verdict, pass_no):
                seen_sources.append(Path(source))
                return root / f"workflow-{pass_no}.json"

            generated = iter(["candidates/r1.png", "candidates/r2.png"])
            verdicts = iter([
                {"pass": False, "score": 45, "defects": ["same"], "preserve": []},
                {"pass": False, "score": 45, "defects": ["same"], "preserve": []},
                {"pass": False, "score": 45, "defects": ["same"], "preserve": []},
            ])

            with (
                patch.object(gallery, "ROOT", root),
                patch.object(gallery, "reload_authority", return_value={}),
                patch.object(gallery, "review_image", side_effect=lambda *a, **k: next(verdicts)),
                patch.object(gallery, "prepare_edit", side_effect=fake_prepare_edit),
                patch.object(gallery, "execute_candidate", side_effect=lambda *a, **k: next(generated)),
            ):
                gallery.refine_candidate(
                    cli=object(),
                    client=object(),
                    config={"vision_reviewer": {"max_refinement_passes": 2}},
                    page={"page_id": "X-01"},
                    candidate_no=1,
                    seed=100,
                    initial=initial,
                )

            self.assertEqual(seen_sources[0], initial)
            self.assertEqual(seen_sources[1], root / "web" / "candidates" / "r1.png")

    def test_identity_failure_regenerates_from_text_instead_of_editing_bad_image(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "web" / "candidates").mkdir(parents=True)
            initial = root / "initial.png"
            initial.write_bytes(b"x")

            generated = root / "web" / "candidates" / "regen.png"
            generated.write_bytes(b"y")
            prepare_calls = []
            edit_calls = []

            verdicts = iter([
                {
                    "pass": False,
                    "score": 40,
                    "stage": "identity",
                    "defects": ["wrong body plan"],
                    "preserve": ["stone wall"],
                },
                {
                    "pass": True,
                    "score": 95,
                    "stage": "quality",
                    "defects": [],
                    "preserve": ["correct anatomy"],
                },
            ])

            def fake_prepare(cli, config, page, seed, candidate_no, review_feedback=None):
                prepare_calls.append(review_feedback)
                return root / "workflow.json"

            with (
                patch.object(gallery, "ROOT", root),
                patch.object(gallery, "reload_authority", return_value={}),
                patch.object(gallery, "review_image", side_effect=lambda *a, **k: next(verdicts)),
                patch.object(gallery, "prepare", side_effect=fake_prepare),
                patch.object(gallery, "prepare_edit", side_effect=lambda *a, **k: edit_calls.append(a)),
                patch.object(gallery, "execute_candidate", return_value="candidates/regen.png"),
            ):
                gallery.refine_candidate(
                    cli=object(),
                    client=object(),
                    config={"vision_reviewer": {"max_refinement_passes": 2}},
                    page={"page_id": "X-01"},
                    candidate_no=1,
                    seed=100,
                    initial=initial,
                )

            self.assertEqual(len(prepare_calls), 1)
            self.assertEqual(edit_calls, [])
            self.assertEqual(prepare_calls[0]["stage"], "identity")
            self.assertEqual(prepare_calls[0]["routing_recommendation"], "regenerate")

    def test_repeated_identity_failure_rotates_composition_on_fresh_regeneration(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "web" / "candidates").mkdir(parents=True)
            initial = root / "initial.png"
            initial.write_bytes(b"x")
            r1 = root / "web" / "candidates" / "r1.png"
            r2 = root / "web" / "candidates" / "r2.png"
            r1.write_bytes(b"1")
            r2.write_bytes(b"2")

            verdicts = iter([
                {"pass": False, "score": 40, "stage": "identity", "defects": ["wrong species"], "preserve": []},
                {"pass": False, "score": 41, "stage": "identity", "defects": ["still wrong species"], "preserve": []},
                {"pass": True, "score": 95, "stage": "quality", "defects": [], "preserve": []},
            ])
            feedbacks = []
            generated = iter(["candidates/r1.png", "candidates/r2.png"])

            def fake_prepare(cli, config, page, seed, candidate_no, review_feedback=None):
                feedbacks.append(dict(review_feedback or {}))
                return root / f"workflow-{len(feedbacks)}.json"

            with (
                patch.object(gallery, "ROOT", root),
                patch.object(gallery, "reload_authority", return_value={}),
                patch.object(gallery, "review_image", side_effect=lambda *a, **k: next(verdicts)),
                patch.object(gallery, "prepare", side_effect=fake_prepare),
                patch.object(gallery, "execute_candidate", side_effect=lambda *a, **k: next(generated)),
            ):
                gallery.refine_candidate(
                    cli=object(),
                    client=object(),
                    config={"vision_reviewer": {"max_refinement_passes": 2}},
                    page={"page_id": "X-01"},
                    candidate_no=1,
                    seed=100,
                    initial=initial,
                )

            self.assertEqual(len(feedbacks), 2)
            self.assertNotIn("composition_escape_offset", feedbacks[0])
            self.assertEqual(feedbacks[1]["composition_escape_offset"], 2)
            self.assertTrue(feedbacks[1]["stagnation_escalation"])

    def test_scene_failure_still_uses_image_edit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "web" / "candidates").mkdir(parents=True)
            initial = root / "initial.png"
            initial.write_bytes(b"x")
            edited = root / "web" / "candidates" / "edit.png"
            edited.write_bytes(b"y")

            verdicts = iter([
                {
                    "pass": False,
                    "score": 40,
                    "stage": "scene",
                    "defects": ["missing spiral stair"],
                    "preserve": ["ogre anatomy"],
                },
                {
                    "pass": True,
                    "score": 95,
                    "stage": "quality",
                    "defects": [],
                    "preserve": ["scene fixed"],
                },
            ])
            edit_sources = []

            def fake_edit(cli, client, config, page, seed, candidate_no, source, verdict, pass_no):
                edit_sources.append(Path(source))
                return root / "workflow.json"

            with (
                patch.object(gallery, "ROOT", root),
                patch.object(gallery, "reload_authority", return_value={}),
                patch.object(gallery, "review_image", side_effect=lambda *a, **k: next(verdicts)),
                patch.object(gallery, "prepare_edit", side_effect=fake_edit),
                patch.object(gallery, "execute_candidate", return_value="candidates/edit.png"),
            ):
                gallery.refine_candidate(
                    cli=object(),
                    client=object(),
                    config={"vision_reviewer": {"max_refinement_passes": 2}},
                    page={"page_id": "X-01"},
                    candidate_no=1,
                    seed=100,
                    initial=initial,
                )

            self.assertEqual(edit_sources, [initial])

    def test_reviewer_only_recheck_reuses_pixels_except_identity_failure(self):
        self.assertFalse(
            gallery.reuse_existing_image_after_reviewer_recheck({
                "pass": False,
                "stage": "identity",
            })
        )
        for stage in ("environment", "scene", "action", "quality"):
            self.assertTrue(
                gallery.reuse_existing_image_after_reviewer_recheck({
                    "pass": False,
                    "stage": stage,
                }),
                stage,
            )
        self.assertFalse(
            gallery.reuse_existing_image_after_reviewer_recheck({
                "pass": True,
                "stage": "quality",
            })
        )

    def test_review_gate_progress_beats_higher_score_from_earlier_failure(self):
        identity_fail = {
            "pass": False,
            "stage": "identity",
            "score": 49,
            "defects": ["wrong creature"],
        }
        environment_fail = {
            "pass": False,
            "stage": "environment",
            "score": 45,
            "defects": ["wrong room"],
        }
        action_fail = {
            "pass": False,
            "stage": "action",
            "score": 42,
            "defects": ["missing action"],
        }
        quality_fail = {
            "pass": False,
            "stage": "quality",
            "score": 40,
            "defects": ["too dense"],
        }
        self.assertGreater(gallery.verdict_rank(environment_fail), gallery.verdict_rank(identity_fail))
        self.assertGreater(gallery.verdict_rank(action_fail), gallery.verdict_rank(environment_fail))
        self.assertGreater(gallery.verdict_rank(quality_fail), gallery.verdict_rank(action_fail))

    def test_repeated_action_failure_escalates_from_edit_to_fresh_regeneration(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "web" / "candidates").mkdir(parents=True)
            initial = root / "initial.png"
            initial.write_bytes(b"x")
            edited = root / "web" / "candidates" / "edit.png"
            edited.write_bytes(b"y")
            regenerated = root / "web" / "candidates" / "regen.png"
            regenerated.write_bytes(b"z")

            verdicts = iter([
                {
                    "pass": False,
                    "score": 45,
                    "stage": "action",
                    "defects": ["lantern is not being kicked"],
                    "preserve": ["goblin anatomy"],
                },
                {
                    "pass": False,
                    "score": 45,
                    "stage": "action",
                    "defects": ["lantern is still not being kicked"],
                    "preserve": ["goblin anatomy"],
                },
                {
                    "pass": True,
                    "score": 95,
                    "stage": "quality",
                    "defects": [],
                    "preserve": ["action fixed"],
                },
            ])

            edit_calls = []
            prepare_feedback = []
            generated = iter(["candidates/edit.png", "candidates/regen.png"])

            def fake_edit(cli, client, config, page, seed, candidate_no, source, verdict, pass_no):
                edit_calls.append((Path(source), pass_no))
                return root / f"edit-{pass_no}.json"

            def fake_prepare(cli, config, page, seed, candidate_no, review_feedback=None):
                prepare_feedback.append(review_feedback)
                return root / "regen.json"

            with (
                patch.object(gallery, "ROOT", root),
                patch.object(gallery, "reload_authority", return_value={}),
                patch.object(gallery, "review_image", side_effect=lambda *a, **k: next(verdicts)),
                patch.object(gallery, "prepare_edit", side_effect=fake_edit),
                patch.object(gallery, "prepare", side_effect=fake_prepare),
                patch.object(gallery, "execute_candidate", side_effect=lambda *a, **k: next(generated)),
            ):
                gallery.refine_candidate(
                    cli=object(),
                    client=object(),
                    config={"vision_reviewer": {"max_refinement_passes": 3}},
                    page={"page_id": "X-01"},
                    candidate_no=1,
                    seed=100,
                    initial=initial,
                )

            self.assertEqual(edit_calls, [(initial, 1)])
            self.assertEqual(len(prepare_feedback), 1)
            self.assertEqual(prepare_feedback[0]["stage"], "action")
            self.assertTrue(prepare_feedback[0]["stagnation_escalation"])
            self.assertEqual(prepare_feedback[0]["routing_recommendation"], "regenerate")

    def test_assistant_rejection_stage_is_forwarded_to_fresh_generation(self):
        prior = {
            "status": "assistant_rejected",
            "assistant_review": {
                "decision": "reject",
                "stage": "identity",
                "notes": "wrong body plan",
            },
        }
        assistant_review = prior.get("assistant_review") or {}
        notes = (assistant_review.get("notes") or "").strip()
        stage = str(assistant_review.get("stage") or "").strip().lower()
        feedback = {
            "text": notes or "Previous candidate was rejected during visual review. Rebuild the failed composition.",
            "routing_recommendation": "regenerate",
        }
        if stage in {"identity", "environment", "action", "quality"}:
            feedback["stage"] = stage

        self.assertEqual(feedback["stage"], "identity")
        self.assertEqual(feedback["routing_recommendation"], "regenerate")
        self.assertEqual(feedback["text"], "wrong body plan")

    def test_expanding_canary_state_to_multi_candidate_clears_auto_selection(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "state.json"
            state_path.write_text(json.dumps({
                "schema_version": 3,
                "copies_per_page": 1,
                "results": [{
                    "page_id": "I-01",
                    "candidate": 1,
                    "status": "ready_for_review",
                    "assistant_review": {
                        "decision": "approve",
                        "review_id": "I-01-C01-Habc",
                    },
                }],
                "selections": {
                    "I-01": {
                        "candidate": 1,
                        "source": "assistant_review",
                        "review_id": "I-01-C01-Habc",
                    }
                },
            }), encoding="utf-8")
            with patch.object(gallery, "STATE_FILE", state_path):
                state = gallery.load_or_init_state(4, False)

            self.assertEqual(state["copies_per_page"], 4)
            self.assertEqual(state["selections"], {})
            self.assertEqual(
                state["results"][0]["assistant_review"]["decision"],
                "approve",
            )

    def test_expanding_to_multi_candidate_preserves_explicit_selection(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "state.json"
            state_path.write_text(json.dumps({
                "schema_version": 3,
                "copies_per_page": 1,
                "results": [],
                "selections": {
                    "I-01": {
                        "candidate": 1,
                        "source": "assistant_selected",
                        "review_id": "I-01-C01-Habc",
                    }
                },
            }), encoding="utf-8")
            with patch.object(gallery, "STATE_FILE", state_path):
                state = gallery.load_or_init_state(4, False)

            self.assertEqual(state["copies_per_page"], 4)
            self.assertEqual(
                state["selections"]["I-01"]["source"],
                "assistant_selected",
            )

    def test_resume_preserves_results_and_selections(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "state.json"
            state_path.write_text(json.dumps({
                "schema_version": 2,
                "copies_per_page": 2,
                "results": [{"page_id": "I-01", "candidate": 1, "status": "ready_for_review"}],
                "selections": {"I-01": {"candidate": 1}},
                "completed_at": "old"
            }), encoding="utf-8")
            with patch.object(gallery, "STATE_FILE", state_path):
                state = gallery.load_or_init_state(4, False)
            self.assertEqual(state["copies_per_page"], 4)
            self.assertEqual(len(state["results"]), 1)
            self.assertEqual(state["selections"]["I-01"]["candidate"], 1)
            self.assertNotIn("completed_at", state)


if __name__ == "__main__":
    unittest.main()
