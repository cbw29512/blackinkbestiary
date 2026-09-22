from __future__ import annotations

import json
from pathlib import Path

try:
    from .environment_variation import family_variation_errors, load_variation_registry
    from .monster_catalog_audit import audit_monster_catalog
except ImportError:
    from environment_variation import family_variation_errors, load_variation_registry
    from monster_catalog_audit import audit_monster_catalog


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_environment_variation_catalog(root: Path) -> dict:
    family_dir = root / "data" / "environment_families"
    registry_path = root / "data" / "environment_variation_families.json"
    errors = []
    family_ids = set()

    for path in sorted(family_dir.glob("*.json")):
        try:
            family = _read(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: invalid environment family JSON: {exc}")
            continue
        family_id = str(family.get("family_id") or "").strip()
        if not family_id:
            errors.append(f"{path.name}: missing family_id")
            continue
        family_ids.add(family_id)

    try:
        registry = load_variation_registry(registry_path)
    except RuntimeError as exc:
        errors.append(str(exc))
        registry = {"families": {}}

    registry_ids = set((registry.get("families") or {}).keys())
    for family_id in sorted(family_ids):
        errors.extend(family_variation_errors(family_id, registry))
    for family_id in sorted(registry_ids - family_ids):
        errors.append(f"variation registry has unknown environment family {family_id!r}")

    return {
        "pass": not errors,
        "environment_families": len(family_ids),
        "variation_families": len(registry_ids),
        "errors": errors,
    }


__all__ = ["audit_monster_catalog", "audit_environment_variation_catalog"]
