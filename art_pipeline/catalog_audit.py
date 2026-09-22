from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

try:
    from .monster_catalog import load_monster_contract, minimal_recipe_errors, resolve_monster_spec
except ImportError:
    from monster_catalog import load_monster_contract, minimal_recipe_errors, resolve_monster_spec

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

    return {
        "pass": not errors,
        "monster_specs": len(specs),
        "repeated_families": sorted(repeated),
        "family_profiles": family_profiles,
        "errors": errors,
    }
