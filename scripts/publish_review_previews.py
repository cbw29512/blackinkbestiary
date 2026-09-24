from __future__ import annotations

import hashlib
import importlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


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

    sources = []
    for source in sorted(SOURCE_DIR.glob("*.png")):
        match = CANDIDATE_RE.match(source.name)
        if not match:
            continue
        sources.append((source, match.group("page"), int(match.group("candidate"))))

    print(f"Found {len(sources)} finalized gallery PNGs; local state has {len(state.get('results', []))} result records.")

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

    MANIFEST.write_text(json.dumps({
        "schema_version": 2,
        "candidate_count": len(published),
        "candidates": published,
    }, indent=2) + "\n", encoding="utf-8")

    if not published:
        statuses = Counter(str(item.get("status") or "unknown") for item in state.get("results", []))
        if statuses:
            print("No finalized PNGs were found. State statuses: " + ", ".join(f"{k}={v}" for k, v in sorted(statuses.items())))
        print(f"Expected finalized images under: {SOURCE_DIR}")

    run("git", "add", "review-previews")
    status = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if status.returncode == 0:
        print(f"Review previews already published locally: {len(published)} candidates")
        return 0

    run("git", "commit", "-m", "Publish coloring book review previews")
    try:
        run("git", "push")
    except subprocess.CalledProcessError:
        print("Previews were committed locally, but git push failed.")
        print("Run: git push")
        return 1

    print(f"Published {len(published)} review previews to GitHub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
