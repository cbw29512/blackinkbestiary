from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def run(cwd: Path, *args: str) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def output(cwd: Path, *args: str) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def publish_snapshot_once(
    repo_root: Path,
    source_dir: Path,
    live_head: str,
    review_branch: str,
) -> str:
    """Publish review files without changing the engine checkout or branch history."""
    with tempfile.TemporaryDirectory(prefix="blackink-review-publish-") as temp_dir:
        worktree = Path(temp_dir) / "worktree"
        run(repo_root, "git", "worktree", "add", "--detach", str(worktree), live_head)
        try:
            target = worktree / "review-previews"
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source_dir, target)

            # The engine branch deliberately ignores review-previews. Force-add
            # them only inside this detached publication worktree.
            run(worktree, "git", "add", "-f", "-A", "--", "review-previews")
            changed = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=worktree,
                check=False,
            ).returncode != 0
            if not changed:
                return live_head

            run(
                worktree,
                "git",
                "-c",
                "user.name=Black Ink Bestiary",
                "-c",
                "user.email=blackink@local",
                "commit",
                "-m",
                "Publish coloring book review previews",
            )
            publish_head = output(worktree, "git", "rev-parse", "HEAD")
            run(
                worktree,
                "git",
                "push",
                f"--force-with-lease=refs/heads/{review_branch}:{live_head}",
                "origin",
                f"{publish_head}:refs/heads/{review_branch}",
            )
            return publish_head
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=repo_root,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=repo_root,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
