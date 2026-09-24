from __future__ import annotations

import hashlib
import importlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from review_publish_git import REVIEW_BRANCH, publish_preview_snapshot


def load_pillow():
    try:
        from PIL import Image
        return Image
    except ModuleNotFoundError:
        print(f"Pillow is required for lightweight GitHub review previews. Installing it into: {sys.executable}")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "Pillow"],
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise SystemExit(
                f"Could not install Pillow into the active Python ({sys.executable}). "
                f"Run: \"{sys.executable}\" -m pip install Pillow"
            ) from exc
        importlib.invalidate_caches()
        try:
            from PIL import Image
            return Image
        except ModuleNotFoundError as exc:
            raise SystemExit(
                f"Pillow installed but is still not importable by the active Python ({sys.executable}). "
                "Close this window, reopen PowerShell, and rerun PUBLISH_REVIEW_PREVIEWS.bat."
            ) from exc


Image = load_pillow()

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "test-gallery-state.json"
RUNTIME_STATUS = ROOT / "data" / "local-runtime-status.json"
SOURCE_DIR = ROOT / "web" / "test-gallery"
PREVIEW_DIR = ROOT / "review-previews"
MANIFEST = PREVIEW_DIR / "manifest.json"
CANDIDATE_RE = re.compile(r"^(?P<page>.+)-C(?P<candidate>\d+)\.png$", re.IGNORECASE)


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verdict_rank(verdict: dict) -> tuple:
    stage = str(verdict.get("stage") or "").strip().lower()
    stage_progress = {
        "identity": 1,
        "environment": 2,
        "scene": 2,
        "action": 3,
        "quality": 4,
    }.get(stage, 0)
    return (
        1 if verdict.get("pass") else 0,
        stage_progress,
        int(verdict.get("score") or 0),
        -len(verdict.get("defects") or []),
    )


def current_reviewable_keys(state: dict) -> set[tuple[str, int]]:
    allowed = {"ready_for_review", "max_refinements_reached"}
    return {
        (str(item.get("page_id")), int(item.get("candidate") or 0))
        for item in state.get("results", [])
        if item.get("page_id")
        and int(item.get("candidate") or 0) > 0
        and str(item.get("status") or "") in allowed
    }


def existing_history_source(item: dict) -> Path | None:
    candidates = []
    for step in item.get("pass_history") or []:
        image = str(step.get("image") or "").strip()
        if not image:
            continue
        path = Path(image)
        if not path.is_absolute():
            path = ROOT / "web" / path
        if path.exists() and path.is_file():
            candidates.append((verdict_rank(step.get("review") or {}), path))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


def restore_final_from_history(item: dict) -> Path | None:
    page_id = str(item.get("page_id") or "")
    candidate = int(item.get("candidate") or 0)
    if not page_id or candidate < 1:
        return None
    destination = SOURCE_DIR / f"{page_id}-C{candidate:02d}.png"
    if destination.exists():
        return destination
    source = existing_history_source(item)
    if source is None:
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


def main() -> int:
    state = {"results": [], "selections": {}}
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)

    metadata = {
        (str(item.get("page_id")), int(item.get("candidate") or 0)): item
        for item in state.get("results", [])
        if item.get("page_id") and int(item.get("candidate") or 0) > 0
    }

    restored = 0
    reviewable = [
        item for item in state.get("results", [])
        if item.get("status") in {"ready_for_review", "max_refinements_reached"}
    ]
    for item in reviewable:
        page_id = str(item.get("page_id") or "")
        candidate = int(item.get("candidate") or 0)
        if not page_id or candidate < 1:
            continue
        destination = SOURCE_DIR / f"{page_id}-C{candidate:02d}.png"
        if not destination.exists() and restore_final_from_history(item):
            restored += 1

    reviewable_keys = current_reviewable_keys(state)

    sources = []
    for source in sorted(SOURCE_DIR.glob("*.png")):
        match = CANDIDATE_RE.match(source.name)
        if not match:
            continue
        key = (match.group("page"), int(match.group("candidate")))
        # Local directories can retain historical PNGs across runs. Current
        # gallery state is authoritative; orphan files must never reappear in
        # the GitHub review snapshot.
        if key not in reviewable_keys:
            continue
        sources.append((source, key[0], key[1]))

    print(
        f"Found {len(sources)} finalized gallery PNGs"
        f" ({restored} restored from pass history); "
        f"local state has {len(state.get('results', []))} result records."
    )

    if not sources and reviewable:
        statuses = Counter(str(item.get("status") or "unknown") for item in state.get("results", []))
        history_images = sum(len(item.get("pass_history") or []) for item in reviewable)
        print("State statuses: " + ", ".join(f"{k}={v}" for k, v in sorted(statuses.items())))
        print(f"Reviewable records contain {history_images} pass-history image references.")
        raise SystemExit(
            "Reviewable gallery records exist, but none of their finalized or pass-history image files still exist locally. "
            "The publisher will not replace the GitHub manifest with an empty gallery."
        )

    published = []
    active_preview_names = set()
    for source, page_id, candidate in sources:
        item = metadata.get((page_id, candidate), {})
        digest = sha256_file(source)
        name = f"{page_id}-C{candidate:02d}.jpg"
        target = PREVIEW_DIR / name
        active_preview_names.add(name)

        with Image.open(source) as im:
            im = im.convert("RGB")
            im.thumbnail((768, 1024))
            im.save(target, "JPEG", quality=82, optimize=True)

        published.append({
            "review_id": f"{page_id}-C{candidate:02d}-H{digest[:16]}",
            "page_id": page_id,
            "monster_name": item.get("monster_name"),
            "candidate": candidate,
            "seed": item.get("seed"),
            "preview": f"review-previews/{name}",
            "source_image": source.relative_to(ROOT / "web").as_posix(),
            "source_sha256": digest,
            "visual_review": item.get("visual_review"),
            "status": item.get("status"),
            "finished_at": item.get("finished_at"),
        })

    for stale in PREVIEW_DIR.glob("*.jpg"):
        if stale.name not in active_preview_names:
            stale.unlink()

    diagnostics = []
    for item in state.get("results", []):
        status = str(item.get("status") or "")
        if status in {"ready_for_review", "max_refinements_reached"}:
            continue
        diagnostics.append({
            "page_id": item.get("page_id"),
            "monster_name": item.get("monster_name"),
            "candidate": item.get("candidate"),
            "status": status,
            "error": item.get("error"),
            "started_at": item.get("started_at"),
            "finished_at": item.get("finished_at"),
            "visual_review": item.get("visual_review"),
        })

    runtime = None
    if RUNTIME_STATUS.exists():
        try:
            runtime = json.loads(RUNTIME_STATUS.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            runtime = {
                "schema_version": 1,
                "status": "failed",
                "stage": "runtime-status-read",
                "message": f"Could not read local runtime status: {exc}",
            }

    if runtime and str(runtime.get("status") or "").lower() == "failed":
        diagnostics.append({
            "page_id": None,
            "monster_name": None,
            "candidate": None,
            "status": "local_runtime_failed",
            "error": runtime.get("message"),
            "stage": runtime.get("stage"),
            "started_at": None,
            "finished_at": runtime.get("updated_at"),
            "visual_review": None,
        })

    MANIFEST.write_text(json.dumps({
        "schema_version": 4,
        "candidate_count": len(published),
        "diagnostic_count": len(diagnostics),
        "runtime": runtime,
        "candidates": published,
        "diagnostics": diagnostics,
    }, indent=2) + "\n", encoding="utf-8")

    try:
        publish_preview_snapshot(ROOT)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Review preview publication failed: {exc}")
        return 1

    print(
        f"Published {len(published)} review previews to GitHub branch "
        f"{REVIEW_BRANCH}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
