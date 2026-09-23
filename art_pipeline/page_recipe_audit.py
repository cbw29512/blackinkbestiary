from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load page-recipe audit input: %s", path)
        raise RuntimeError(f"Could not load page-recipe audit input {path}: {exc}") from exc


def audit_manifest_recipe_debt(
    root: Path,
    manifest_path: Path,
) -> dict:
    contract = _read_json(root / "config" / "universal_page_contract.json")
    authority = contract.get("generation_authority") or {}
    legacy_fields = set(authority.get("legacy_non_authoritative_fields") or [])
    strip_now = set(authority.get("strip_now_fields") or [])
    retained = set(authority.get("runtime_compatibility_retained") or [])
    required_paths = list(contract.get("required_unique_fields") or [])
    manifest = _read_json(manifest_path)

    field_counts: Counter[str] = Counter()
    pages_with_legacy: list[dict] = []
    missing_authority: list[dict] = []

    for page in manifest.get("pages") or []:
        present = sorted(field for field in legacy_fields if field in page)
        for field in present:
            field_counts[field] += 1
        if present:
            pages_with_legacy.append({
                "page_id": page.get("page_id"),
                "fields": present,
            })

        missing = []
        for dotted in required_paths:
            value = page
            for part in dotted.split("."):
                if not isinstance(value, dict) or part not in value:
                    value = None
                    break
                value = value[part]
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(dotted)
        if missing:
            missing_authority.append({
                "page_id": page.get("page_id"),
                "missing": missing,
            })

    total_pages = len(manifest.get("pages") or [])
    strip_now_counts = {
        field: field_counts.get(field, 0)
        for field in sorted(strip_now)
    }
    retained_counts = {
        field: field_counts.get(field, 0)
        for field in sorted(retained)
    }
    return {
        "manifest": manifest_path.relative_to(root).as_posix(),
        "total_pages": total_pages,
        "pages_with_legacy_fields": len(pages_with_legacy),
        "legacy_field_counts": dict(sorted(field_counts.items())),
        "strip_now_field_counts": strip_now_counts,
        "runtime_compatibility_retained_counts": retained_counts,
        "legacy_pages": pages_with_legacy,
        "pages_missing_authoritative_fields": missing_authority,
        "safe_to_strip_generation_legacy": not missing_authority,
        "migration_complete": not pages_with_legacy and not missing_authority,
    }
