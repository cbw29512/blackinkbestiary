from __future__ import annotations

import json
from pathlib import Path

try:
    from .monster_catalog import family_profile_path, load_monster_contract
except ImportError:
    from monster_catalog import family_profile_path, load_monster_contract


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_monster_recipes(root: Path) -> dict:
    monster_dir = root / "data" / "monsters"
    family_dir = root / "data" / "monster_families"
    contract = load_monster_contract(root / "config" / "universal_monster_contract.json")
    policy = contract.get("recipe_policy") or {}
    allowed = set(policy.get("allowed_top_level") or [])
    forbidden = set(policy.get("forbidden_in_v3") or [])

    errors: list[str] = []
    warnings: list[str] = []
    minimal = 0
    migration_candidates = 0
    standalone_legacy = 0
    total = 0
    family_refs: dict[str, int] = {}

    for path in sorted(monster_dir.glob("*.json")):
        total += 1
        data = _read(path)
        monster_id = str(data.get("monster_id") or path.stem)
        schema = int(data.get("schema_version") or 1)
        family_path = family_profile_path(data, family_dir)
        family_id = str(data.get("family_profile") or "").strip()

        if family_id:
            family_refs[family_id] = family_refs.get(family_id, 0) + 1

        if schema >= 3:
            minimal += 1
            extra = sorted(set(data) - allowed)
            bad = sorted(set(data) & forbidden)
            if extra:
                errors.append(f"{monster_id}: schema-v3+ recipe has unapproved fields: {', '.join(extra)}")
            if bad:
                errors.append(f"{monster_id}: schema-v3+ recipe duplicates family-owned fields: {', '.join(bad)}")
            if not family_path:
                errors.append(f"{monster_id}: schema-v3+ recipe requires valid family_profile")
            if "visual_overrides" in data and not data["visual_overrides"]:
                errors.append(f"{monster_id}: empty visual_overrides should be omitted")
            if "scene_overrides" in data and not data["scene_overrides"]:
                errors.append(f"{monster_id}: empty scene_overrides should be omitted")
        elif family_path:
            migration_candidates += 1
            warnings.append(f"{monster_id}: legacy recipe already has family_profile and should migrate")
        else:
            standalone_legacy += 1

    return {
        "pass": not errors,
        "total_monsters": total,
        "minimal_v3_plus": minimal,
        "legacy_with_family_profile": migration_candidates,
        "standalone_legacy": standalone_legacy,
        "family_profiles_referenced": len(family_refs),
        "family_reference_counts": dict(sorted(family_refs.items())),
        "errors": errors,
        "warnings": warnings,
    }
