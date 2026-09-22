from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from book_registry import get_book, book_setup_status
from manifest_validation import validate_manifest
from state_validation import validate_state

CONFIG_FILE = ROOT / "config" / "studio.json"
MONSTER_DIR = ROOT / "data" / "monsters"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely activate a registered Black-Ink book.")
    parser.add_argument("book_id", help="Example: TOME-II")
    args = parser.parse_args()

    book = get_book(args.book_id)
    status = book_setup_status(book, ROOT)
    if not status["production_files_complete"]:
        print(f"REFUSED: {book['book_id']} — {book['title']} is setup-ready, not production-ready.")
        print(json.dumps(status, indent=2))
        return 2

    manifest_path = ROOT / book["manifest_path"]
    state_path = ROOT / book["state_path"]
    tome = _read(manifest_path)
    state = _read(state_path)

    errors = validate_manifest(ROOT, tome, MONSTER_DIR) + validate_state(tome, state)
    if errors:
        print("REFUSED: production audit failed.")
        for error in errors:
            print(f"- {error}")
        return 3

    config = _read(CONFIG_FILE)
    config["active_book"] = {
        "manifest": book["manifest_path"],
        "state": book["state_path"],
        "reviews": book["reviews_path"],
    }
    _write(CONFIG_FILE, config)
    print(f"ACTIVE: {book['book_id']} — {book['title']}")
    print("Restart the Studio server to load the selected book.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
