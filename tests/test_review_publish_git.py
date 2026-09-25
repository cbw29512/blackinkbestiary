import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import review_publish_git as rpg


class ReviewPublishGitTests(unittest.TestCase):
    def test_stage_snapshot_includes_synced_live_decisions(self):
        root = Path("C:/fake")
        with patch.object(rpg, "run") as run:
            rpg.stage_preview_snapshot(root)

        run.assert_called_once_with(root, "git", "add", "-A", "review-previews")

    def test_sync_live_decisions_fetches_validated_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            calls = []
            payload = '{"schema_version":1,"reviews":[{"review_id":"X","decision":"reject"}]}'

            def fake_output(_root, *args):
                key = tuple(args)
                if key == ("git", "rev-parse", "origin/review-previews-live"):
                    return "live123"
                if key == (
                    "git",
                    "show",
                    "origin/review-previews-live:review-previews/decisions.json",
                ):
                    return payload
                raise KeyError(key)

            with (
                patch.object(rpg, "run", side_effect=lambda root_arg, *args: calls.append((root_arg, args))),
                patch.object(rpg, "output", side_effect=fake_output),
            ):
                head = rpg.sync_live_decisions(root)

            self.assertEqual(head, "live123")
            saved = json.loads((root / "review-previews" / "decisions.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["reviews"][0]["review_id"], "X")
            self.assertIn(
                (
                    root,
                    (
                        "git",
                        "fetch",
                        "origin",
                        "review-previews-live:refs/remotes/origin/review-previews-live",
                    ),
                ),
                calls,
            )

    def test_publish_uses_dedicated_review_branch_and_resyncs_engine(self):
        root = Path("C:/fake")
        outputs = {
            ("git", "branch", "--show-current"): "feat/environment-spatial-hardening",
            ("git", "rev-parse", "HEAD"): "abc123",
        }

        def fake_output(_root, *args):
            return outputs[tuple(args)]

        calls = []
        with (
            patch.object(rpg, "output", side_effect=fake_output),
            patch.object(rpg, "tracked_changes_outside_previews", return_value=[]),
            patch.object(rpg, "sync_live_decisions", return_value="live-before"),
            patch.object(rpg, "stage_preview_snapshot"),
            patch.object(rpg, "run", side_effect=lambda root_arg, *args: calls.append((root_arg, args))),
            patch.object(rpg.subprocess, "run", return_value=SimpleNamespace(returncode=1)),
        ):
            result = rpg.publish_preview_snapshot(root)

        self.assertEqual(result, "abc123")
        self.assertIn(
            (
                root,
                (
                    "git",
                    "push",
                    "--force-with-lease=refs/heads/review-previews-live:live-before",
                    "origin",
                    "abc123:refs/heads/review-previews-live",
                ),
            ),
            calls,
        )
        self.assertIn(
            (root, ("git", "fetch", "origin", "feat/environment-spatial-hardening")),
            calls,
        )
        self.assertIn(
            (
                root,
                (
                    "git",
                    "reset",
                    "--hard",
                    "origin/feat/environment-spatial-hardening",
                ),
            ),
            calls,
        )

    def test_unchanged_snapshot_does_not_repoint_live_branch(self):
        root = Path("C:/fake")
        outputs = {
            ("git", "branch", "--show-current"): "feat/environment-spatial-hardening",
        }

        def fake_output(_root, *args):
            return outputs[tuple(args)]

        calls = []
        with (
            patch.object(rpg, "output", side_effect=fake_output),
            patch.object(rpg, "tracked_changes_outside_previews", return_value=[]),
            patch.object(rpg, "sync_live_decisions", return_value="live-before"),
            patch.object(rpg, "stage_preview_snapshot"),
            patch.object(rpg, "run", side_effect=lambda root_arg, *args: calls.append((root_arg, args))),
            patch.object(rpg.subprocess, "run", return_value=SimpleNamespace(returncode=0)),
        ):
            result = rpg.publish_preview_snapshot(root)

        self.assertEqual(result, "live-before")
        self.assertFalse(any(args[:2] == ("git", "push") for _, args in calls))
        self.assertIn(
            (root, ("git", "fetch", "origin", "feat/environment-spatial-hardening")),
            calls,
        )

    def test_publish_preserves_local_edits_but_removes_temporary_preview_commit(self):
        root = Path("C:/fake")
        heads = iter(["base123", "preview456"])

        def fake_output(_root, *args):
            if tuple(args) == ("git", "branch", "--show-current"):
                return "feat/environment-spatial-hardening"
            if tuple(args) == ("git", "rev-parse", "HEAD"):
                return next(heads)
            raise KeyError(tuple(args))

        calls = []
        with (
            patch.object(rpg, "output", side_effect=fake_output),
            patch.object(rpg, "tracked_changes_outside_previews", return_value=[" M scripts/local.py"]),
            patch.object(rpg, "sync_live_decisions", return_value="live-before"),
            patch.object(rpg, "stage_preview_snapshot"),
            patch.object(rpg, "run", side_effect=lambda root_arg, *args: calls.append((root_arg, args))),
            patch.object(rpg.subprocess, "run", return_value=SimpleNamespace(returncode=1)),
        ):
            result = rpg.publish_preview_snapshot(root)

        self.assertEqual(result, "preview456")
        self.assertIn(
            (
                root,
                (
                    "git",
                    "push",
                    "--force-with-lease=refs/heads/review-previews-live:live-before",
                    "origin",
                    "preview456:refs/heads/review-previews-live",
                ),
            ),
            calls,
        )
        self.assertIn((root, ("git", "reset", "--mixed", "base123")), calls)
        self.assertFalse(any(args[:2] == ("git", "fetch") for _, args in calls))
        self.assertFalse(
            any(args[:3] == ("git", "reset", "--hard") for _, args in calls)
        )


if __name__ == "__main__":
    unittest.main()
