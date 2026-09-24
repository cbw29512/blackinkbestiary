from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path


def load_pillow():
    try:
        from PIL import Image
        return Image
    except ModuleNotFoundError:
        print("Pillow is required for lightweight GitHub review previews. Installing it automatically...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--user", "Pillow"],
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise SystemExit(
                "Could not install Pillow automatically. Run: python -m pip install --user Pillow"
            ) from exc
        importlib.invalidate_caches()
        from PIL import Image
        return Image


Image = load_pillow()

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "test-gallery-state.json"
SOURCE_DIR = ROOT / "web" / "test-gallery"
PREVIEW_DIR = ROOT / "review-previews"
MANIFEST = PREVIEW_DIR / "manifest.json"


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    if not STATE.exists():
        raise SystemExit("No test gallery state found. Run RUN_COLORING_BOOK.bat first.")

    state = json.loads(STATE.read_text(encoding="utf-8"))
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    published = []
    active_preview_names = set()
    for item in state.get("results", []):
        if item.get("status") not in {"ready_for_review", "max_refinements_reached"}:
            continue
        image_path = item.get("image_path")
        if not image_path:
            continue
        source = ROOT / "web" / image_path
        if not source.exists():
            continue

        name = f"{item['page_id']}-C{int(item['candidate']):02d}.jpg"
        target = PREVIEW_DIR / name
        active_preview_names.add(name)
        with Image.open(source) as im:
            im = im.convert("RGB")
            im.thumbnail((768, 1024))
            im.save(target, "JPEG", quality=82, optimize=True)

        review_id = f"{item['page_id']}-C{int(item['candidate']):02d}-S{item.get('seed')}"
        published.append({
            "review_id": review_id,
            "page_id": item.get("page_id"),
            "monster_name": item.get("monster_name"),
            "candidate": item.get("candidate"),
            "seed": item.get("seed"),
            "preview": f"review-previews/{name}",
            "source_image": image_path,
            "visual_review": item.get("visual_review"),
            "finished_at": item.get("finished_at"),
        })

    for stale in PREVIEW_DIR.glob("*.jpg"):
        if stale.name not in active_preview_names:
            stale.unlink()

    MANIFEST.write_text(json.dumps({
        "schema_version": 1,
        "candidate_count": len(published),
        "candidates": published,
    }, indent=2) + "\n", encoding="utf-8")

    run("git", "add", "review-previews")
    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=ROOT,
    )
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
