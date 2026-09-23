from __future__ import annotations

from copy import deepcopy
from pathlib import Path

try:
    from .page_contract import missing_required_paths
except ImportError:
    from page_contract import missing_required_paths


PLAN_ONLY_KEYS = {"planning_status"}


def build_manifest_from_plan(plan: dict, root: Path) -> tuple[dict, list[str]]:
    errors = []
    slots = plan.get("slots") or []
    target = int(plan.get("target_pages") or 0)
    if target <= 0:
        errors.append("target_pages must be positive")
    if len(slots) != target:
        errors.append("slot count does not match target_pages")

    pages = []
    for slot in slots:
        page_id = str(slot.get("page_id") or "<missing>")
        missing = missing_required_paths(slot, root)
        if missing:
            errors.append(f"{page_id}: missing contract fields: {', '.join(missing)}")
            continue
        if slot.get("planning_status") == "unassigned":
            errors.append(f"{page_id}: planning_status is still unassigned")
            continue
        page = {
            key: deepcopy(value)
            for key, value in slot.items()
            if key not in PLAN_ONLY_KEYS
        }
        pages.append(page)

    manifest = {
        "tome_id": plan.get("book_id"),
        "title": plan.get("title"),
        "theme": plan.get("theme", ""),
        "total_pages": target,
        "page_contract": plan.get("page_contract", "black-ink-page-v2"),
        "pages": pages,
    }
    return manifest, errors
