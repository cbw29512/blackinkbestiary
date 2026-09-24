import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import review_publish_git as rpg


class ReviewPublishGitTests(unittest.TestCase):
    def test_stage_snapshot_never_stages_decisions(self):
        root = Path("C:/fake")
        with (
            patch.object(rpg, "run") as run,
            patch.object(rpg.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as subprocess_run,
        ):
            rpg.stage_preview_snapshot(root)

        run.assert_called_once_with(root, "git", "add", "-A", "review-previews")
        subprocess_run.assert_called_once_with(
            ["git", "restore", "--staged", "review-previews/decisions.json"],
            cwd=root,
            check=False,
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
                    "--force",
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
            ("git", "rev-parse", "origin/review-previews-live"): "live123",
        }

        def fake_output(_root, *args):
            return outputs[tuple(args)]

        calls = []
        with (
            patch.object(rpg, "output", side_effect=fake_output),
            patch.object(rpg, "tracked_changes_outside_previews", return_value=[]),
            patch.object(rpg, "stage_preview_snapshot"),
            patch.object(rpg, "run", side_effect=lambda root_arg, *args: calls.append((root_arg, args))),
            patch.object(rpg.subprocess, "run", return_value=SimpleNamespace(returncode=0)),
        ):
            result = rpg.publish_preview_snapshot(root)

        self.assertEqual(result, "live123")
        self.assertFalse(any(args[:2] == ("git", "push") for _, args in calls))
        self.assertIn(
            (root, ("git", "fetch", "origin", "feat/environment-spatial-hardening")),
            calls,
        )

    def test_publish_does_not_resync_when_other_tracked_changes_exist(self):
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
            patch.object(rpg, "tracked_changes_outside_previews", return_value=[" M scripts/local.py"]),
            patch.object(rpg, "stage_preview_snapshot"),
            patch.object(rpg, "run", side_effect=lambda root_arg, *args: calls.append((root_arg, args))),
            patch.object(rpg.subprocess, "run", return_value=SimpleNamespace(returncode=1)),
        ):
            rpg.publish_preview_snapshot(root)

        self.assertFalse(any(args[:2] == ("git", "reset") for _, args in calls))


if __name__ == "__main__":
    unittest.main()
