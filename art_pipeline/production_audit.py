from __future__ import annotations

import json
from pathlib import Path

try:
    from .manifest_validation import validate_manifest
    from .state_validation import validate_state
    from .studio_config import active_book_paths
except ImportError:
    from manifest_validation import validate_manifest
    from state_validation import validate_state
    from studio_config import active_book_paths


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_active_book(root: Path) -> dict:
    paths = active_book_paths(root)
    checks = []
    errors = []

    for label in ("manifest", "state", "quality_rules", "page_archetypes", "environment_standard"):
        path = paths[label]
        ok = path.exists() and path.is_file()
        checks.append({"check": f"{label}_exists", "pass": ok, "path": str(path)})
        if not ok:
            errors.append(f"{label} missing: {path}")

    if errors:
        return {"pass": False, "checks": checks, "errors": errors}

    tome = _read(paths["manifest"])
    state = _read(paths["state"])
    manifest_errors = validate_manifest(root, tome, root / "data" / "monsters")
    state_errors = validate_state(tome, state)

    checks.append({
        "check": "manifest_valid",
        "pass": not manifest_errors,
        "details": manifest_errors,
    })
    checks.append({
        "check": "state_valid",
        "pass": not state_errors,
        "details": state_errors,
    })

    approved = sum(
        1 for entry in state.get("pages", {}).values()
        if entry.get("status") == "locked"
    )
    return {
        "pass": not manifest_errors and not state_errors,
        "book_id": tome.get("tome_id"),
        "title": tome.get("title"),
        "total_pages": tome.get("total_pages"),
        "approved_pages": approved,
        "current_page_id": state.get("current_page_id"),
        "checks": checks,
        "errors": manifest_errors + state_errors,
    }
