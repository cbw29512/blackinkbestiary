import json
import subprocess
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
                if key == (
                    "git",
                    "show",
                    "origin/review-previews-live:review-previews/quality-history.jsonl",
                ):
                    raise subprocess.CalledProcessError(128, key)
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
                        "+review-previews-live:refs/remotes/origin/review-previews-live",
                    ),
                ),
                calls,
            )

    def test_quality_history_records_signed_deltas_and_contract_baselines(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            preview = root / "review-previews"
            preview.mkdir()
            history = {
                "quality_contract_version": "v1",
                "quality_contract_fingerprint": "same",
                "active_book_id": "TOME-I",
                "engine_commit": "old",
                "measurement_fingerprint": "old-measurement",
                "metrics": {
                    "visual_cleanliness": 70.0,
                    "semantic_accuracy": 20.0,
                    "replication_readiness": 80.0,
                },
                "defect_counts": {"IDENTITY_HEROIC_BULK": 5},
                "generation_efficiency": {
                    "avg_gpu_attempts_per_page": 5.0,
                    "semantic_yield_percent": 10.0,
                },
            }
            (preview / "quality-history.jsonl").write_text(
                json.dumps(history) + "\n",
                encoding="utf-8",
            )
            current = {
                **history,
                "engine_commit": "new",
                "measurement_fingerprint": "new-measurement",
                "metrics": {
                    "visual_cleanliness": 60.0,
                    "semantic_accuracy": 35.0,
                    "replication_readiness": 85.0,
                },
                "defect_counts": {"IDENTITY_HEROIC_BULK": 2},
                "generation_efficiency": {
                    "avg_gpu_attempts_per_page": 3.5,
                    "semantic_yield_percent": 20.0,
                },
            }
            (preview / "quality-current.json").write_text(
                json.dumps(current),
                encoding="utf-8",
            )

            self.assertTrue(rpg.append_quality_snapshot(root))
            trend = json.loads((preview / "quality-trend.json").read_text(encoding="utf-8"))
            self.assertTrue(trend["comparable_to_previous"])
            self.assertEqual(trend["comparisons"]["visual_cleanliness"]["signed_delta"], "-10.0")
            self.assertEqual(trend["comparisons"]["semantic_accuracy"]["signed_delta"], "+15.0")
            self.assertEqual(trend["comparisons"]["replication_readiness"]["signed_delta"], "+5.0")
            self.assertEqual(trend["comparisons"]["visual_cleanliness"]["trend"], "regressing")
            self.assertEqual(
                trend["defect_comparisons"]["IDENTITY_HEROIC_BULK"]["signed_delta"],
                "-3",
            )
            self.assertEqual(
                trend["defect_comparisons"]["IDENTITY_HEROIC_BULK"]["trend"],
                "improving",
            )
            self.assertEqual(
                trend["efficiency_comparisons"]["avg_gpu_attempts_per_page"]["signed_delta"],
                "-1.50",
            )
            self.assertEqual(
                trend["efficiency_comparisons"]["avg_gpu_attempts_per_page"]["trend"],
                "improving",
            )
            self.assertEqual(
                trend["efficiency_comparisons"]["semantic_yield_percent"]["signed_delta"],
                "+10.00",
            )

            changed = dict(current)
            changed["quality_contract_fingerprint"] = "new-contract"
            changed["measurement_fingerprint"] = "contract-reset"
            (preview / "quality-current.json").write_text(json.dumps(changed), encoding="utf-8")
            self.assertTrue(rpg.append_quality_snapshot(root))
            reset = json.loads((preview / "quality-trend.json").read_text(encoding="utf-8"))
            self.assertFalse(reset["comparable_to_previous"])
            self.assertIn("new baseline", reset["comparison_reason"])

    def test_publish_uses_isolated_worktree_without_mutating_engine_checkout(self):
        root = Path("C:/fake")
        with (
            patch.object(rpg, "output", return_value="feat/environment-spatial-hardening"),
            patch.object(rpg, "sync_live_decisions", return_value="live-before"),
            patch.object(rpg, "append_quality_snapshot"),
            patch.object(rpg, "publish_snapshot_once", return_value="preview123") as publish_once,
            patch.object(rpg, "run") as engine_run,
        ):
            result = rpg.publish_preview_snapshot(root)

        self.assertEqual(result, "preview123")
        publish_once.assert_called_once_with(
            root,
            root / "review-previews",
            "live-before",
            "review-previews-live",
        )
        engine_run.assert_not_called()

    def test_publish_retries_once_after_review_branch_race(self):
        root = Path("C:/fake")
        sync_heads = iter(["live-before", "live-after"])
        failure = subprocess.CalledProcessError(1, ["git", "push"])
        with (
            patch.object(rpg, "output", return_value="feat/environment-spatial-hardening"),
            patch.object(rpg, "sync_live_decisions", side_effect=lambda _root: next(sync_heads)),
            patch.object(rpg, "append_quality_snapshot"),
            patch.object(
                rpg,
                "publish_snapshot_once",
                side_effect=[failure, "retry789"],
            ) as publish_once,
        ):
            result = rpg.publish_preview_snapshot(root)

        self.assertEqual(result, "retry789")
        self.assertEqual(publish_once.call_count, 2)
        self.assertEqual(publish_once.call_args_list[0].args[2], "live-before")
        self.assertEqual(publish_once.call_args_list[1].args[2], "live-after")

    def test_worktree_publisher_force_adds_ignored_preview_state(self):
        helper = (ROOT / "scripts" / "review_publish_worktree.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"worktree", "add", "--detach"', helper)
        self.assertIn('"git", "add", "-f", "-A"', helper)
        self.assertIn("--force-with-lease=refs/heads/", helper)
        self.assertIn('"worktree", "remove", "--force"', helper)


if __name__ == "__main__":
    unittest.main()
