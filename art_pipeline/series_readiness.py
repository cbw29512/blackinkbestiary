from __future__ import annotations

import json
from pathlib import Path

try:
    from .book_registry import load_series, plan_path
    from .manifest_validation import validate_manifest
    from .page_contract import missing_required_paths, page_uniqueness_fingerprint
    from .state_validation import validate_state
    from .source_scope import load_monster_registry
except ImportError:
    from book_registry import load_series, plan_path
    from manifest_validation import validate_manifest
    from page_contract import missing_required_paths, page_uniqueness_fingerprint
    from state_validation import validate_state
    from source_scope import load_monster_registry


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _plan_progress(plan: dict, root: Path) -> dict:
    slots = plan.get("slots") or []
    ready = 0
    blocked = []
    for slot in slots:
        missing = missing_required_paths(slot, root)
        if slot.get("planning_status") == "unassigned":
            missing = ["planning_status"] + missing
        if missing:
            blocked.append({
                "page_id": slot.get("page_id"),
                "missing": sorted(set(missing)),
            })
        else:
            ready += 1
    return {
        "slots": len(slots),
        "recipe_ready": ready,
        "recipe_blocked": len(blocked),
        "blockers": blocked[:10],
    }


def audit_series(root: Path) -> dict:
    series = load_series(root / "data" / "series.json")
    rows = []
    structural_errors = []

    for book in series["books"]:
        manifest_path = root / book["manifest_path"]
        state_path = root / book["state_path"]
        reviews_path = root / book["reviews_path"]
        row = {
            "book_id": book["book_id"],
            "title": book["title"],
            "registry_status": book["status"],
            "target_pages": book["target_pages"],
            "production_ready": False,
            "manifest_exists": manifest_path.exists(),
            "state_exists": state_path.exists(),
            "reviews_exists": reviews_path.exists(),
        }

        if manifest_path.exists() and state_path.exists():
            manifest = _read(manifest_path)
            state = _read(state_path)
            manifest_errors = validate_manifest(
                root, manifest, root / "data" / "monsters"
            )
            state_errors = validate_state(manifest, state)
            row["manifest_errors"] = manifest_errors
            row["state_errors"] = state_errors
            row["production_ready"] = not manifest_errors and not state_errors
            row["recipe_ready"] = len(manifest.get("pages", []))
            row["recipe_blocked"] = 0
        else:
            ppath = plan_path(book["book_id"], root / "data" / "book_plans")
            row["plan_exists"] = ppath.exists()
            if ppath.exists():
                row.update(_plan_progress(_read(ppath), root))
            else:
                row.update({"slots": 0, "recipe_ready": 0, "recipe_blocked": book["target_pages"]})

        if book["status"] == "production" and not row["production_ready"]:
            structural_errors.append(
                f"{book['book_id']}: registry says production but production audit fails"
            )
        if row.get("recipe_ready", 0) > book["target_pages"]:
            structural_errors.append(
                f"{book['book_id']}: ready recipe count exceeds target_pages"
            )
        rows.append(row)

    registry = load_monster_registry(root)
    allowed = set((registry.get("monsters") or {}).keys())
    used = set()
    cross_book_recipes = {}
    for row in rows:
        if row.get("manifest_exists"):
            book = next(item for item in series["books"] if item["book_id"] == row["book_id"])
            manifest = _read(root / book["manifest_path"])
            used.update(page.get("monster_spec_id") for page in manifest.get("pages", []))
            for page in manifest.get("pages", []):
                try:
                    fingerprint = page_uniqueness_fingerprint(page, root)
                except RuntimeError:
                    continue
                prior = cross_book_recipes.get(fingerprint)
                if prior and prior != book["book_id"]:
                    structural_errors.append(
                        f"{book['book_id']}:{page.get('page_id')}: duplicate resolved page recipe already used in {prior}"
                    )
                else:
                    cross_book_recipes[fingerprint] = book["book_id"]
    unknown = sorted(item for item in used if item and item not in allowed)
    if unknown:
        structural_errors.append("production manifests use monsters outside source roster: " + ", ".join(unknown))

    return {
        "pass": not structural_errors,
        "series_id": series.get("series_id"),
        "books_registered": len(rows),
        "source_registry_entries": len(allowed),
        "production_ready_books": sum(1 for row in rows if row["production_ready"]),
        "books": rows,
        "errors": structural_errors,
    }
