from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_BRANCH = "feat/environment-spatial-hardening"
REVIEW_BRANCH = "review-previews-live"
DECISIONS_RELATIVE = "review-previews/decisions.json"
DECISIONS_PATH = ROOT / DECISIONS_RELATIVE


def output(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def git_returncode(*args: str) -> int:
    return subprocess.run(
        args,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode


def changed_paths(base: str, head: str) -> list[str]:
    text = output("git", "diff", "--name-only", f"{base}..{head}")
    return [line.strip().replace("\\", "/") for line in text.splitlines() if line.strip()]


def preview_only_paths(paths: list[str]) -> bool:
    return bool(paths) and all(path.startswith("review-previews/") for path in paths)


def sync_review_decisions() -> bool:
    """Import only exact-image review decisions from the dedicated review branch."""
    remote_ref = f"origin/{REVIEW_BRANCH}"
    try:
        print(f"Fetching latest AI review decisions from {REVIEW_BRANCH}...")
        run(
            "git",
            "fetch",
            "origin",
            f"+{REVIEW_BRANCH}:refs/remotes/origin/{REVIEW_BRANCH}",
        )
        payload = output("git", "show", f"{remote_ref}:{DECISIONS_RELATIVE}")
        parsed = json.loads(payload)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"Could not synchronize AI review decisions: {exc}")
        return False

    reviews = parsed.get("reviews") if isinstance(parsed, dict) else None
    if not isinstance(reviews, list):
        print("Could not synchronize AI review decisions: reviews must be a JSON list.")
        return False

    DECISIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DECISIONS_PATH.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")
    print(f"AI review decisions synchronized: {len(reviews)} exact-image review records.")
    return True


def finish_success() -> int:
    return 0 if sync_review_decisions() else 1


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
    # Exact-image decisions are re-imported from the dedicated review branch
    # after engine synchronization, so stale local preview files are disposable.
    subprocess.run(
        ["git", "restore", "--staged", "--worktree", "review-previews"],
        cwd=ROOT,
        check=False,
    )

    print(f"Fetching latest {ENGINE_BRANCH}...")
    run("git", "fetch", "origin", ENGINE_BRANCH)

    remote_ref = f"origin/{ENGINE_BRANCH}"
    local_head = output("git", "rev-parse", "HEAD")
    remote_head = output("git", "rev-parse", remote_ref)

    if local_head == remote_head:
        print(f"Engine already synchronized at {output('git', 'rev-parse', '--short', 'HEAD')}.")
        return finish_success()

    if git_returncode("git", "merge-base", "--is-ancestor", local_head, remote_head) == 0:
        run("git", "merge", "--ff-only", remote_ref)
        print(f"Engine synchronized at {output('git', 'rev-parse', '--short', 'HEAD')}.")
        return finish_success()

    if git_returncode("git", "merge-base", "--is-ancestor", remote_head, local_head) == 0:
        local_only = changed_paths(remote_head, local_head)
        if preview_only_paths(local_only):
            print("Removing legacy local preview-only commit(s) from the engine branch...")
            run("git", "reset", "--hard", remote_ref)
            print(f"Engine synchronized at {output('git', 'rev-parse', '--short', 'HEAD')}.")
            return finish_success()
        print("Refusing automatic sync because the local engine branch contains non-preview commits not on origin.")
        for path in local_only:
            print("  " + path)
        return 1

    merge_base = output("git", "merge-base", local_head, remote_head)
    local_only = changed_paths(merge_base, local_head)
    if preview_only_paths(local_only):
        print("Recovering from legacy preview-only branch divergence...")
        run("git", "reset", "--hard", remote_ref)
        print(f"Engine synchronized at {output('git', 'rev-parse', '--short', 'HEAD')}.")
        return finish_success()

    print("Refusing automatic sync because the local and remote engine branches diverged in source code.")
    for path in local_only:
        print("  " + path)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
