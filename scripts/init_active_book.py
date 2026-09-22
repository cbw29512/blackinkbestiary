from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from manifest_validation import validate_manifest
from production_state_factory import build_production_state
from studio_config import active_book_paths

MONSTER_DIR = ROOT / "data" / "monsters"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the active coloring book production state.")
    parser.add_argument("--force", action="store_true", help="Replace an existing active-book state file.")
    args = parser.parse_args()

    paths = active_book_paths(ROOT)
    tome = read_json(paths["manifest"])
    errors = validate_manifest(ROOT, tome, MONSTER_DIR)
    if errors:
        print("ACTIVE BOOK INVALID")
        for error in errors:
            print(f"- {error}")
        return 2

    state_path = paths["state"]
    if state_path.exists() and not args.force:
        print(f"State already exists: {state_path}")
        print("Use --force only when intentionally starting this book over.")
        return 1

    write_json(state_path, build_production_state(tome))
    paths["reviews"].parent.mkdir(parents=True, exist_ok=True)
    paths["reviews"].touch(exist_ok=True)
    print(f"READY: {tome['title']} ({tome['total_pages']} pages)")
    print(f"State: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
