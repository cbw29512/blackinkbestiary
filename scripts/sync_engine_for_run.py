from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_BRANCH = "feat/environment-spatial-hardening"


def output(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def tracked_changes_outside_previews() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
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


def main() -> int:
    current = output("git", "branch", "--show-current")
    if current != ENGINE_BRANCH:
        print(
            f"Engine sync requires branch {ENGINE_BRANCH!r}; "
            f"current branch is {current!r}."
        )
        return 1

    outside = tracked_changes_outside_previews()
    if outside:
        print("Refusing automatic engine sync because tracked non-preview edits exist:")
        for line in outside:
            print("  " + line)
        print("Commit/stash those edits before running the canary.")
        return 1

    # Preview JPG/manifest changes are disposable generated handoff state.
    # Exact-image decisions are fetched from the engine branch below, so the
    # workstation should never preserve a stale local copy over GitHub.
    subprocess.run(
        ["git", "restore", "--staged", "--worktree", "review-previews"],
        cwd=ROOT,
        check=False,
    )

    print(f"Fetching latest {ENGINE_BRANCH}...")
    run("git", "fetch", "origin", ENGINE_BRANCH)
    run("git", "merge", "--ff-only", f"origin/{ENGINE_BRANCH}")
    print(f"Engine synchronized at {output('git', 'rev-parse', '--short', 'HEAD')}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
