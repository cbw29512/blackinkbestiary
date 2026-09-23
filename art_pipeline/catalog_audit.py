from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

try:
    from .environment_variation import family_variation_errors, load_variation_registry
    from .monster_catalog import load_monster_contract, minimal_recipe_errors, resolve_monster_spec
    from .monster_recipe_audit import audit_monster_recipes
except ImportError:
    from environment_variation import family_variation_errors, load_variation_registry
    from monster_catalog import load_monster_contract, minimal_recipe_errors, resolve_monster_spec
    from monster_recipe_audit import audit_monster_recipes


def _missing_paths(payload: dict, paths) -> list[str]:
    missing = []
    for dotted in paths or []:
        value = payload
        for part in str(dotted).split("."):
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]
        if value is None or value == "" or value == []:
            missing.append(str(dotted))
    return missing


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_monster_catalog(root: Path) -> dict:
    monster_dir = root / "data" / "monsters"
    family_dir = root / "data" / "monster_families"
    specs = []
    groups: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    errors: list[str] = []

    for path in sorted(monster_dir.glob("*.json")):
        try:
            spec = _read(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue
        specs.append((path, spec))
        errors.extend(minimal_recipe_errors(path.stem, monster_dir, family_dir))
        try:
            resolve_monster_spec(path.stem, monster_dir, family_dir)
        except RuntimeError as exc:
            errors.append(f"{path.name}: could not resolve through universal engine: {exc}")
        family = str(spec.get("family_profile") or spec.get("family") or "").strip()
        if family:
            groups[family].append((path, spec))

        profile_id = str(spec.get("family_profile") or "").strip()
        if profile_id:
            profile_path = family_dir / f"{profile_id}.json"
            if not profile_path.exists():
                errors.append(f"{path.name}: family_profile {profile_id!r} does not exist")

    repeated = {family: items for family, items in groups.items() if len(items) >= 2}
    for family, items in sorted(repeated.items()):
        for path, spec in items:
            profile_id = str(spec.get("family_profile") or "").strip()
            if not profile_id:
                errors.append(
                    f"{path.name}: repeated family {family!r} requires family_profile"
                )

    try:
        contract = load_monster_contract(root / "config" / "universal_monster_contract.json")
        required_family_paths = contract.get("family_profile_required") or []
    except RuntimeError as exc:
        errors.append(f"monster contract could not be loaded: {exc}")
        required_family_paths = []

    family_profiles = 0
    for path in sorted(family_dir.glob("*.json")):
        family_profiles += 1
        try:
            profile = _read(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: invalid family JSON: {exc}")
            continue
        if profile.get("profile_id") != path.stem:
            errors.append(f"{path.name}: profile_id must match filename")
        missing = _missing_paths(profile, required_family_paths)
        if missing:
            errors.append(f"{path.name}: missing family DNA fields: {', '.join(missing)}")

    recipe_report = audit_monster_recipes(root)
    errors.extend(f"monster recipe: {error}" for error in recipe_report["errors"])

    return {
        "pass": not errors,
        "monster_specs": len(specs),
        "minimal_v3_plus": recipe_report["minimal_v3_plus"],
        "legacy_with_family_profile": recipe_report["legacy_with_family_profile"],
        "standalone_legacy": recipe_report["standalone_legacy"],
        "repeated_families": sorted(repeated),
        "family_profiles": family_profiles,
        "errors": errors,
    }


def audit_environment_variation_catalog(root: Path) -> dict:
    family_dir = root / "data" / "environment_families"
    registry_path = root / "data" / "environment_variation_families.json"
    errors: list[str] = []
    family_ids: set[str] = set()

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
