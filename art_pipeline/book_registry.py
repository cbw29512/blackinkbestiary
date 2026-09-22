from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERIES_FILE = ROOT / "data" / "series.json"
PLAN_DIR = ROOT / "data" / "book_plans"


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load book registry file {path}: {exc}") from exc


def load_series(path: Path = SERIES_FILE) -> dict:
    payload = _read(path)
    if not payload.get("books"):
        raise RuntimeError("Series registry contains no books")
    return payload


def get_book(book_id: str, path: Path = SERIES_FILE) -> dict:
    wanted = str(book_id or "").strip().upper()
    for book in load_series(path)["books"]:
        if str(book.get("book_id") or "").upper() == wanted:
            return book
    raise RuntimeError(f"Unknown book ID: {book_id}")


def plan_path(book_id: str, plan_dir: Path = PLAN_DIR) -> Path:
    slug = str(book_id).lower()
    return plan_dir / f"{slug}.json"


def book_setup_status(book: dict, root: Path = ROOT) -> dict:
    manifest = root / book["manifest_path"]
    state = root / book["state_path"]
    reviews = root / book["reviews_path"]
    plan = plan_path(book["book_id"], root / "data" / "book_plans")
    return {
        "book_id": book["book_id"],
        "title": book["title"],
        "registry_status": book["status"],
        "plan_exists": plan.exists() if book["book_id"] != "TOME-I" else True,
        "manifest_exists": manifest.exists(),
        "state_exists": state.exists(),
        "reviews_exists": reviews.exists(),
        "production_files_complete": manifest.exists() and state.exists(),
    }


def series_status(root: Path = ROOT) -> list[dict]:
    return [book_setup_status(book, root) for book in load_series(root / "data" / "series.json")["books"]]
