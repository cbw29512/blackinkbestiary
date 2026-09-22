from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from book_scaffold import build_book_plan, build_book_record, normalize_book_slug


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a new Black-Ink coloring book.")
    parser.add_argument("book_id")
    parser.add_argument("title")
    parser.add_argument("--theme", default="")
    parser.add_argument("--pages", type=int, default=50)
    parser.add_argument("--prefix", required=True, help="Page prefix, e.g. IX or HOL")
    parser.add_argument(
        "--environment-scope",
        default="",
        help="Comma-separated environment scope labels",
    )
    args = parser.parse_args()

    series_path = ROOT / "data" / "series.json"
    series = _read(series_path)
    if any(book["book_id"].lower() == args.book_id.lower() for book in series["books"]):
        print(f"REFUSED: {args.book_id} is already registered.")
        return 2

    scope = [item.strip() for item in args.environment_scope.split(",") if item.strip()]
    book = build_book_record(args.book_id, args.title, args.theme, args.pages, scope)
    plan = build_book_plan(book, args.prefix.upper())

    series["books"].append(book)
    _write(series_path, series)

    slug = normalize_book_slug(args.book_id)
    plan_path = ROOT / "data" / "book_plans" / f"{slug}.json"
    _write(plan_path, plan)

    print(f"REGISTERED: {args.book_id} — {args.title}")
    print(f"Pages: {args.pages}")
    print(f"Plan: {plan_path}")
    print("This book is setup-ready only. Fill every page recipe before promotion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
