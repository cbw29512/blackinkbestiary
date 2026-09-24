from __future__ import annotations

import subprocess
from pathlib import Path

REVIEW_BRANCH = "review-previews-live"


def run(root: Path, *args: str) -> None:
    subprocess.run(args, cwd=root, check=True)


def output(root: Path, *args: str) -> str:
    return subprocess.check_output(args, cwd=root, text=True).strip()


def tracked_changes_outside_previews(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    outside = []
    for raw in result.stdout.splitlines():
        path = raw[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if not path.startswith("review-previews/"):
            outside.append(raw)
    return outside


def stage_preview_snapshot(root: Path) -> None:
    run(root, "git", "add", "-A", "review-previews")
    # Decisions belong to the engine branch and are written by ChatGPT.
    # The local publisher must never overwrite them with a stale copy.
    subprocess.run(
        ["git", "restore", "--staged", "review-previews/decisions.json"],
        cwd=root,
        check=False,
    )


def publish_preview_snapshot(root: Path) -> str:
    engine_branch = output(root, "git", "branch", "--show-current")
    if not engine_branch:
        raise RuntimeError("Review publishing requires a checked-out engine branch")
    safe_to_resync = not tracked_changes_outside_previews(root)
    stage_preview_snapshot(root)

    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=root,
    ).returncode != 0
    pre_publish_head = (
        output(root, "git", "rev-parse", "HEAD")
        if staged
        else ""
    )

    publish_head = ""
    if staged:
        run(root, "git", "commit", "-m", "Publish coloring book review previews")
        publish_head = output(root, "git", "rev-parse", "HEAD")
        run(
            root,
            "git",
            "push",
            "--force",
            "origin",
            f"{publish_head}:refs/heads/{REVIEW_BRANCH}",
        )
    else:
        # Never repoint the live review branch at an engine commit merely
        # because the generated snapshot is unchanged. The prior live snapshot
        # remains the authoritative handoff until new preview bytes exist.
        publish_head = output(root, "git", "rev-parse", f"origin/{REVIEW_BRANCH}")
        print("Review snapshot unchanged; leaving review-previews-live untouched.")

    if safe_to_resync:
        # Generated PNGs and gallery state are untracked; hard-resetting tracked
        # code cannot delete them. This removes any temporary preview commit and
        # catches the workstation up with engine changes made during generation.
        run(root, "git", "fetch", "origin", engine_branch)
        run(root, "git", "reset", "--hard", f"origin/{engine_branch}")
        print(f"Local code resynced to origin/{engine_branch}.")
    else:
        if staged:
            # The preview commit belongs only to review-previews-live. Remove it
            # from the local engine branch without discarding unrelated working
            # tree edits. Preview files may remain modified and are disposable.
            run(root, "git", "reset", "--mixed", pre_publish_head)
        print(
            "Preview snapshot published; unrelated tracked working-tree edits "
            "were preserved, and the temporary preview commit was removed locally."
        )

    return publish_head
