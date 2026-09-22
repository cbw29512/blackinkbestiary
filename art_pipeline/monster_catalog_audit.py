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
    variant_dir = root / "data" / "monster_variants"
    specs = []
    groups = defaultdict(list)
    errors = []

    for path in sorted(monster_dir.glob("*.json")):
        try:
            spec = _read(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue
        specs.append((path, spec))
        if int(spec.get("schema_version") or 1) < 3:
            errors.append(f"{path.name}: legacy monster schema is not allowed")
        forbidden = [
            key for key in (
                "visual_identity", "accuracy_checks", "known_failure_modes",
                "scene_identity", "size", "creature_type", "family"
            ) if key in spec
        ]
        if forbidden:
            errors.append(
                f"{path.name}: monster recipe contains reusable DNA fields: {', '.join(forbidden)}"
            )
        errors.extend(minimal_recipe_errors(path.stem, monster_dir, family_dir, variant_dir))
        try:
            resolve_monster_spec(path.stem, monster_dir, family_dir, variant_dir)
        except RuntimeError as exc:
            errors.append(f"{path.name}: could not resolve through universal engine: {exc}")

        profile_id = str(spec.get("family_profile") or "").strip()
        if not profile_id:
            errors.append(f"{path.name}: every monster requires family_profile")
        elif not (family_dir / f"{profile_id}.json").exists():
            errors.append(f"{path.name}: family_profile {profile_id!r} does not exist")
        else:
            groups[profile_id].append(path.name)

    contract = load_monster_contract(root / "config" / "universal_monster_contract.json")
    required_family_paths = contract.get("family_profile_required") or []
    family_profiles = 0
    for path in sorted(family_dir.glob("*.json")):
        family_profiles += 1
        profile = _read(path)
        if profile.get("profile_id") != path.stem:
            errors.append(f"{path.name}: profile_id must match filename")
        missing = _missing_paths(profile, required_family_paths)
        if missing:
            errors.append(f"{path.name}: missing family DNA fields: {', '.join(missing)}")

    variant_profiles = 0
    for path in sorted(variant_dir.glob("*.json")):
        variant_profiles += 1
        variant = _read(path)
        if variant.get("variant_id") != path.stem:
            errors.append(f"{path.name}: variant_id must match filename")
        family_id = str(variant.get("family_profile") or "").strip()
        if not family_id:
            errors.append(f"{path.name}: variant profile missing family_profile")
        elif not (family_dir / f"{family_id}.json").exists():
            errors.append(f"{path.name}: variant family_profile {family_id!r} does not exist")

    return {
        "pass": not errors,
        "monster_specs": len(specs),
        "minimal_recipe_specs": sum(
            1 for _, spec in specs
            if int(spec.get("schema_version") or 1) >= 3 and "visual_identity" not in spec
        ),
        "variant_backed_specs": sum(1 for _, spec in specs if spec.get("variant_profile")),
        "repeated_families": sorted(k for k, v in groups.items() if len(v) >= 2),
        "family_profiles": family_profiles,
        "variant_profiles": variant_profiles,
        "errors": errors,
    }
