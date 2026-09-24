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
sys.path.insert(0, str(ROOT / "art_pipeline"))

from generation_fingerprint import page_generation_fingerprint, page_review_fingerprint
from page_contract import resolve_page_spec
from studio_config import active_book_paths

STATE = ROOT / "data" / "test-gallery-state.json"
RUNTIME_STATUS = ROOT / "data" / "local-runtime-status.json"
ENGINE_PREFLIGHT_STATUS = ROOT / "data" / "engine-preflight-status.json"
SOURCE_DIR = ROOT / "web" / "test-gallery"
PREVIEW_DIR = ROOT / "review-previews"
MANIFEST = PREVIEW_DIR / "manifest.json"
CANDIDATE_RE = re.compile(r"^(?P<page>.+)-C(?P<candidate>\d+)\.png$", re.IGNORECASE)


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def engine_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


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


def current_authority_fingerprints(root: Path = ROOT) -> dict[str, dict]:
    paths = active_book_paths(root)
    tome = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    result = {}
    for raw in tome.get("pages", []):
        page = resolve_page_spec(raw, root)
        page_id = str(page.get("page_id") or "")
        if not page_id:
            continue
        result[page_id] = {
            "generation": page_generation_fingerprint(page, root),
            "review": page_review_fingerprint(page, root),
        }
    return result


def main() -> int:
    state = {"results": [], "selections": {}}
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    current_authority = current_authority_fingerprints(ROOT)

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

        selection = (state.get("selections") or {}).get(page_id) or {}
        exact_review_id = f"{page_id}-C{candidate:02d}-H{digest[:16]}"
        authority = current_authority.get(page_id) or {}
        generation_authority_current = bool(
            authority.get("generation")
            and str(item.get("generation_fingerprint") or "") == authority["generation"]
        )
        review_authority_current = bool(
            authority.get("review")
            and str(item.get("review_fingerprint") or "") == authority["review"]
        )
        selected = (
            int(selection.get("candidate") or 0) == candidate
            and str(selection.get("review_id") or "") == exact_review_id
            and str(item.get("status") or "") == "ready_for_review"
            and bool((item.get("visual_review") or {}).get("pass"))
            and generation_authority_current
            and review_authority_current
        )
        published.append({
            "review_id": exact_review_id,
            "page_id": page_id,
            "monster_name": item.get("monster_name"),
            "candidate": candidate,
            "selected": selected,
            "seed": item.get("seed"),
            "engine_commit": item.get("engine_commit") or "unknown",
            "generation_fingerprint": item.get("generation_fingerprint") or "unknown",
            "review_fingerprint": item.get("review_fingerprint") or "unknown",
            "generation_authority_current": generation_authority_current,
            "review_authority_current": review_authority_current,
            "review_checked_at": item.get("review_checked_at"),
            "preview": f"review-previews/{name}",
            "source_image": source.relative_to(ROOT / "web").as_posix(),
            "source_sha256": digest,
            "visual_review": item.get("visual_review"),
            "assistant_review": item.get("assistant_review"),
            "status": item.get("status"),
            "finished_at": item.get("finished_at"),
        })

    effective_selections = {}
    for item in published:
        if not item.get("selected"):
            continue
        page_id = str(item.get("page_id") or "")
        if not page_id:
            continue
        selection = (state.get("selections") or {}).get(page_id) or {}
        effective_selections[page_id] = {
            "candidate": int(item.get("candidate") or 0),
            "source": selection.get("source"),
            "review_id": item.get("review_id"),
        }

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
            "engine_commit": item.get("engine_commit") or "unknown",
            "generation_fingerprint": item.get("generation_fingerprint") or "unknown",
            "review_fingerprint": item.get("review_fingerprint") or "unknown",
            "review_checked_at": item.get("review_checked_at"),
            "error": item.get("error"),
            "started_at": item.get("started_at"),
            "finished_at": item.get("finished_at"),
            "visual_review": item.get("visual_review"),
            "assistant_review": item.get("assistant_review"),
        })

    engine_preflight = None
    if ENGINE_PREFLIGHT_STATUS.exists():
        try:
            engine_preflight = json.loads(
                ENGINE_PREFLIGHT_STATUS.read_text(encoding="utf-8-sig")
            )
        except (OSError, json.JSONDecodeError) as exc:
            engine_preflight = {
                "schema_version": 1,
                "status": "failed",
                "stage": "engine-preflight-status-read",
                "message": f"Could not read engine preflight status: {exc}",
            }

    if engine_preflight and str(engine_preflight.get("status") or "").lower() == "failed":
        diagnostics.append({
            "page_id": None,
            "monster_name": None,
            "candidate": None,
            "status": "engine_preflight_failed",
            "error": "Local engine/unit-test preflight failed",
            "stage": engine_preflight.get("stage"),
            "started_at": engine_preflight.get("started_at"),
            "finished_at": engine_preflight.get("updated_at"),
            "output_tail": engine_preflight.get("output_tail"),
            "visual_review": None,
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
        "schema_version": 5,
        "snapshot_engine_commit": engine_commit(),
        "candidate_count": len(published),
        "diagnostic_count": len(diagnostics),
        "runtime": runtime,
        "engine_preflight": engine_preflight,
        "selections": effective_selections,
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
