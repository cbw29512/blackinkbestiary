from __future__ import annotations

import json
import logging
from pathlib import Path

try:
    from .monster_catalog import family_profile_path, load_monster_contract
except ImportError:
    from monster_catalog import family_profile_path, load_monster_contract

LOGGER = logging.getLogger(__name__)


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load monster recipe: %s", path)
        raise RuntimeError(f"Could not load monster recipe {path}: {exc}") from exc


def audit_monster_recipes(root: Path) -> dict:
    monster_dir = root / "data" / "monsters"
    family_dir = root / "data" / "monster_families"
    errors: list[str] = []
    warnings: list[str] = []

    try:
        contract = load_monster_contract(
            root / "config" / "universal_monster_contract.json"
        )
    except RuntimeError as exc:
        LOGGER.exception("Could not load universal monster contract")
        return {
            "pass": False,
            "total_monsters": 0,
            "minimal_v3_plus": 0,
            "legacy_with_family_profile": 0,
            "standalone_legacy": 0,
            "family_profiles_referenced": 0,
            "family_reference_counts": {},
            "errors": [f"monster contract could not be loaded: {exc}"],
            "warnings": [],
        }

    policy = contract.get("recipe_policy") or {}
    allowed = set(policy.get("allowed_top_level") or [])
    forbidden = set(policy.get("forbidden_in_v3") or [])
    required = list(contract.get("minimal_recipe_required") or [])

    minimal = 0
    migration_candidates = 0
    standalone_legacy = 0
    total = 0
    family_refs: dict[str, int] = {}

    for path in sorted(monster_dir.glob("*.json")):
        total += 1
        try:
            data = _read(path)
            schema = int(data.get("schema_version") or 1)
        except RuntimeError as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        except (TypeError, ValueError) as exc:
            LOGGER.exception("Invalid schema_version in monster recipe: %s", path)
            errors.append(f"{path.name}: invalid schema_version: {exc}")
            continue

        monster_id = str(data.get("monster_id") or path.stem)
        family_path = family_profile_path(data, family_dir)
        family_id = str(data.get("family_profile") or "").strip()

        if family_id:
            family_refs[family_id] = family_refs.get(family_id, 0) + 1

        if schema >= 3:
            minimal += 1
            missing = [
                field for field in required
                if not str(data.get(field) or "").strip()
            ]
            extra = sorted((set(data) - allowed) - forbidden)
            duplicated = sorted(set(data) & forbidden)

            if missing:
                errors.append(
                    f"{monster_id}: schema-v3+ recipe missing required fields: "
                    + ", ".join(missing)
                )
            if extra:
                errors.append(
                    f"{monster_id}: schema-v3+ recipe has unapproved fields: "
                    + ", ".join(extra)
                )
            if duplicated:
                errors.append(
                    f"{monster_id}: schema-v3+ recipe duplicates family-owned fields: "
                    + ", ".join(duplicated)
                )
            if not family_path:
                errors.append(
                    f"{monster_id}: schema-v3+ recipe requires valid family_profile"
                )
            for field in ("visual_overrides", "scene_overrides"):
                if field in data and not data[field]:
                    errors.append(f"{monster_id}: empty {field} should be omitted")
        elif family_path:
            migration_candidates += 1
            warnings.append(
                f"{monster_id}: legacy recipe already has family_profile and should migrate"
            )
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
