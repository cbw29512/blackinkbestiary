from __future__ import annotations

import json
from pathlib import Path

try:
    from .prompt_builder import build_page_verification_checklist, build_prompt
    from .studio_config import active_book_paths
    from .vision_review_prompts import (
        build_action_review_prompt,
        build_environment_review_prompt,
        build_identity_review_prompt,
        build_review_prompt,
    )
except ImportError:
    from prompt_builder import build_page_verification_checklist, build_prompt
    from studio_config import active_book_paths
    from vision_review_prompts import (
        build_action_review_prompt,
        build_environment_review_prompt,
        build_identity_review_prompt,
        build_review_prompt,
    )

ROOT = Path(__file__).resolve().parents[1]


def _stats(text: str) -> dict:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    duplicate_lines = len(lines) - len(set(lines))
    return {
        "chars": len(text),
        "words": len(text.split()),
        "nonempty_lines": len(lines),
        "duplicate_lines": duplicate_lines,
        "duplicate_line_percent": (
            round(100.0 * duplicate_lines / len(lines), 1) if lines else 0.0
        ),
    }


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def prompt_load_report(root: Path = ROOT, page_ids: list[str] | None = None) -> dict:
    paths = active_book_paths(root)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    pages = list(manifest.get("pages") or [])
    if page_ids is not None:
        wanted = set(page_ids)
        pages = [page for page in pages if str(page.get("page_id") or "") in wanted]

    rows = []
    errors = []
    for page in pages:
        page_id = str(page.get("page_id") or "")
        try:
            generation = build_prompt(page, candidate_no=1)
            checklist = build_page_verification_checklist(page)
            reviews = {
                "identity": build_identity_review_prompt(page),
                "environment": build_environment_review_prompt(page),
                "action": build_action_review_prompt(page),
                "quality": build_review_prompt(page),
            }
            rows.append({
                "page_id": page_id,
                "generation": _stats(generation),
                "review": {name: _stats(value) for name, value in reviews.items()},
                "checklist_items": sum(len(items) for items in checklist.values()),
                "checklist_by_stage": {name: len(items) for name, items in checklist.items()},
            })
        except Exception as exc:
            errors.append({"page_id": page_id, "error": str(exc)})

    standard = json.loads(
        (root / "config" / "coloring_page_standard.json").read_text(encoding="utf-8")
    )
    budget = standard.get("generation_prompt_budget") or {}
    target_max_chars = int(budget.get("target_max_chars") or 12000)
    hard_max_chars = int(budget.get("hard_max_chars") or 14000)
    hard_max_words = int(budget.get("hard_max_words") or 2000)

    generation_chars = [row["generation"]["chars"] for row in rows]
    generation_words = [row["generation"]["words"] for row in rows]
    checklist_items = [row["checklist_items"] for row in rows]
    review_stage_chars = {
        stage: [row["review"][stage]["chars"] for row in rows]
        for stage in ("identity", "environment", "action", "quality")
    }

    return {
        "schema_version": 1,
        "pages_measured": len(rows),
        "errors": errors,
        "generation_chars_avg": _avg(generation_chars),
        "generation_chars_max": max(generation_chars, default=0),
        "generation_words_avg": _avg(generation_words),
        "generation_words_max": max(generation_words, default=0),
        "generation_prompt_budget": {
            "target_max_chars": target_max_chars,
            "hard_max_chars": hard_max_chars,
            "hard_max_words": hard_max_words,
            "within_hard_budget": all(
                row["generation"]["chars"] <= hard_max_chars
                and row["generation"]["words"] <= hard_max_words
                for row in rows
            ),
            "within_target_budget": all(
                row["generation"]["chars"] <= target_max_chars
                for row in rows
            ),
        },
        "checklist_items_avg": _avg(checklist_items),
        "checklist_items_max": max(checklist_items, default=0),
        "review_chars_avg": {
            stage: _avg(values) for stage, values in review_stage_chars.items()
        },
        "review_chars_max": {
            stage: max(values, default=0) for stage, values in review_stage_chars.items()
        },
        "rows": rows,
    }
