from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from book_promotion import build_manifest_from_plan
from book_registry import get_book, plan_path
from manifest_validation import validate_manifest
from production_state_factory import build_production_state


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote a completed book plan into production files.")
    parser.add_argument("book_id")
    args = parser.parse_args()

    book = get_book(args.book_id)
    plan = _read(plan_path(book["book_id"]))
    manifest, errors = build_manifest_from_plan(plan, ROOT)
    if errors:
        print("REFUSED: book plan is incomplete.")
        for error in errors:
            print(f"- {error}")
        return 2

    errors = validate_manifest(ROOT, manifest, ROOT / "data" / "monsters")
    if errors:
        print("REFUSED: generated manifest failed validation.")
        for error in errors:
            print(f"- {error}")
        return 3

    manifest_path = ROOT / book["manifest_path"]
    state_path = ROOT / book["state_path"]
    reviews_path = ROOT / book["reviews_path"]
    if manifest_path.exists() or state_path.exists():
        print("REFUSED: production files already exist.")
        return 4

    _write(manifest_path, manifest)
    _write(state_path, build_production_state(manifest))
    reviews_path.parent.mkdir(parents=True, exist_ok=True)
    reviews_path.touch(exist_ok=True)
    print(f"PRODUCTION READY: {book['book_id']} — {book['title']}")
    print(f"Manifest: {manifest_path}")
    print(f"State: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
