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
    def test_existing_success_is_skipped(self):
        prior = {"status": "ready_for_review"}
        self.assertTrue(gallery.should_skip_candidate(prior, False))
        self.assertTrue(gallery.should_skip_candidate(prior, True))

    def test_failed_candidate_can_be_retried(self):
        prior = {"status": "technical_qa_failed"}
        self.assertTrue(gallery.should_skip_candidate(prior, False))
        self.assertFalse(gallery.should_skip_candidate(prior, True))


    def test_assistant_rejected_candidate_can_be_retried(self):
        prior = {"status": "assistant_rejected"}
        self.assertTrue(gallery.should_skip_candidate(prior, False))
        self.assertFalse(gallery.should_skip_candidate(prior, True))

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
