from __future__ import annotations

from copy import deepcopy


def normalize_book_slug(book_id: str) -> str:
    return str(book_id or "").strip().lower().replace(" ", "-")


def build_book_record(
    book_id: str,
    title: str,
    theme: str,
    target_pages: int,
    environment_scope: list[str],
) -> dict:
    if not book_id or not title:
        raise ValueError("book_id and title are required")
    if target_pages <= 0:
        raise ValueError("target_pages must be positive")
    slug = normalize_book_slug(book_id)
    return {
        "book_id": book_id,
        "title": title,
        "status": "setup_ready",
        "target_pages": target_pages,
        "theme": theme,
        "environment_scope": list(environment_scope),
        "manifest_path": f"data/books/{slug}.json",
        "state_path": f"data/books/{slug}-state.json",
        "reviews_path": f"data/books/{slug}-reviews.jsonl",
        "creature_catalog": "data/monsters",
        "family_catalog": "data/monster_families",
        "environment_catalog": "data/environment_families",
        "page_contract": "config/universal_page_contract.json",
        "style_standard": "docs/STYLE_BIBLE.md",
        "environment_standard": "config/environment_standard.json",
        "coloring_page_standard": "config/coloring_page_standard.json",
    }


def build_page_slot(prefix: str, order: int) -> dict:
    return {
        "page_id": f"{prefix}-{order:02d}",
        "order": order,
        "planning_status": "unassigned",
        "page_contract": "black-ink-page-v1",
        "monster_spec_id": None,
        "moment": None,
        "archetype": None,
        "environment_profile_id": None,
        "environment_variant": {
            "landmark": None,
            "framing": None,
            "interaction": None,
        },
        "physicality": {
            "mode": None,
            "support": None,
            "motion": None,
        },
    }


def build_book_plan(book: dict, page_prefix: str) -> dict:
    target = int(book["target_pages"])
    return {
        "schema_version": 1,
        "book_id": book["book_id"],
        "title": book["title"],
        "status": "setup_ready",
        "target_pages": target,
        "theme": book.get("theme", ""),
        "environment_scope": deepcopy(book.get("environment_scope", [])),
        "page_contract": "black-ink-page-v1",
        "production_contract": {
            "universal": "config/universal_page_contract.json",
            "rule": "Slots store unique page recipe data only; universal and catalog data fill the rest.",
        },
        "slots": [build_page_slot(page_prefix, i) for i in range(1, target + 1)],
    }
