import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_engine_for_run.py"
spec = importlib.util.spec_from_file_location("sync_engine_for_run", SCRIPT)
sync = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(sync)


class SyncEngineForRunTests(unittest.TestCase):
    def test_review_decisions_are_imported_from_dedicated_review_branch(self):
        calls = []
        payload = {
            "schema_version": 1,
            "reviews": [
                {
                    "review_id": "I-01-C01-Habc",
                    "decision": "reject",
                    "notes": "wrong identity",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "review-previews" / "decisions.json"
            with (
                patch.object(sync, "DECISIONS_PATH", destination),
                patch.object(sync, "run", side_effect=lambda *args: calls.append(args)),
                patch.object(sync, "output", return_value=json.dumps(payload)),
            ):
                self.assertTrue(sync.sync_review_decisions())

            saved = json.loads(destination.read_text(encoding="utf-8"))

        self.assertEqual(saved, payload)
        self.assertIn(
            (
                "git",
                "fetch",
                "origin",
                f"+{sync.REVIEW_BRANCH}:refs/remotes/origin/{sync.REVIEW_BRANCH}",
            ),
            calls,
        )

    def test_review_decision_sync_fails_closed_on_invalid_schema(self):
        with (
            patch.object(sync, "run"),
            patch.object(sync, "output", return_value=json.dumps({"schema_version": 1})),
        ):
            self.assertFalse(sync.sync_review_decisions())

    def test_preview_only_path_classifier_is_strict(self):
        self.assertTrue(sync.preview_only_paths([
            "review-previews/manifest.json",
            "review-previews/I-01-C01.jpg",
        ]))
        self.assertFalse(sync.preview_only_paths([]))
        self.assertFalse(sync.preview_only_paths([
            "review-previews/manifest.json",
            "scripts/prompt_builder.py",
        ]))

    def test_local_preview_only_commit_is_removed_and_remote_head_restored(self):
        calls = []

        def fake_output(*args):
            key = tuple(args)
            if key == ("git", "branch", "--show-current"):
                return sync.ENGINE_BRANCH
            if key == ("git", "rev-parse", "HEAD"):
                return "local-preview-head"
            if key == ("git", "rev-parse", f"origin/{sync.ENGINE_BRANCH}"):
                return "remote-engine-head"
            if key == ("git", "rev-parse", "--short", "HEAD"):
                return "remote123"
            raise KeyError(key)

        with (
            patch.object(sync, "output", side_effect=fake_output),
            patch.object(sync, "tracked_changes_outside_previews", return_value=[]),
            patch.object(sync, "git_returncode", side_effect=[1, 0]),
            patch.object(sync, "changed_paths", return_value=["review-previews/manifest.json"]),
            patch.object(sync, "run", side_effect=lambda *args: calls.append(args)),
            patch.object(sync, "sync_review_decisions", return_value=True),
            patch.object(sync.subprocess, "run", return_value=SimpleNamespace(returncode=0)),
        ):
            self.assertEqual(sync.main(), 0)

        self.assertIn(("git", "fetch", "origin", sync.ENGINE_BRANCH), calls)
        self.assertIn(
            ("git", "reset", "--hard", f"origin/{sync.ENGINE_BRANCH}"),
            calls,
        )
        self.assertFalse(any(call[:2] == ("git", "merge") for call in calls))

    def test_local_source_commit_blocks_automatic_reset(self):
        calls = []

        def fake_output(*args):
            key = tuple(args)
            if key == ("git", "branch", "--show-current"):
                return sync.ENGINE_BRANCH
            if key == ("git", "rev-parse", "HEAD"):
                return "local-source-head"
            if key == ("git", "rev-parse", f"origin/{sync.ENGINE_BRANCH}"):
                return "remote-engine-head"
            raise KeyError(key)

        with (
            patch.object(sync, "output", side_effect=fake_output),
            patch.object(sync, "tracked_changes_outside_previews", return_value=[]),
            patch.object(sync, "git_returncode", side_effect=[1, 0]),
            patch.object(sync, "changed_paths", return_value=["art_pipeline/prompt_builder.py"]),
            patch.object(sync, "run", side_effect=lambda *args: calls.append(args)),
            patch.object(sync, "sync_review_decisions", return_value=True),
            patch.object(sync.subprocess, "run", return_value=SimpleNamespace(returncode=0)),
        ):
            self.assertEqual(sync.main(), 1)

        self.assertIn(("git", "fetch", "origin", sync.ENGINE_BRANCH), calls)
        self.assertFalse(
            any(call[:3] == ("git", "reset", "--hard") for call in calls)
        )


if __name__ == "__main__":
    unittest.main()
