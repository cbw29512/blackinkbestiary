from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONSTER_DIR = ROOT / "data" / "monsters"
FAMILY_DIR = ROOT / "data" / "monster_families"
SPECIES_DIR = ROOT / "data" / "monster_species"
CONTRACT_FILE = ROOT / "config" / "universal_monster_contract.json"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load creature catalog file {path}: {exc}") from exc


def _merge_unique(base, override):
    result = []
    for item in list(base or []) + list(override or []):
        if item not in result:
            result.append(item)
    return result


def _merge_dict(base: dict, override: dict | None) -> dict:
    merged = deepcopy(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = _merge_unique(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_monster_contract(path: Path = CONTRACT_FILE) -> dict:
    return _read_json(path)


def family_profile_path(spec: dict, family_dir: Path = FAMILY_DIR) -> Path | None:
    profile_id = str(spec.get("family_profile") or spec.get("family") or "").strip()
    if not profile_id:
        return None
    path = family_dir / f"{profile_id}.json"
    return path if path.exists() else None


def species_profile_path(spec: dict, species_dir: Path = SPECIES_DIR) -> Path | None:
    profile_id = str(spec.get("species_profile") or "").strip()
    if not profile_id:
        return None
    path = species_dir / f"{profile_id}.json"
    return path if path.exists() else None


def _apply_contract_defaults(resolved: dict, contract: dict) -> dict:
    defaults = contract.get("defaults") or {}
    visual_defaults = defaults.get("visual_identity") or {}
    resolved["visual_identity"] = _merge_dict(
        visual_defaults,
        resolved.get("visual_identity") or {},
    )
    resolved["default_habitats"] = _merge_unique(
        defaults.get("default_habitats"),
        resolved.get("default_habitats"),
    )
    resolved["locomotion"] = _merge_dict(
        defaults.get("locomotion") or {},
        resolved.get("locomotion") or {},
    )
    resolved["scene_identity"] = _merge_dict(
        defaults.get("scene_identity") or {},
        resolved.get("scene_identity") or {},
    )
    return resolved


def _apply_minimal_recipe(resolved: dict, raw: dict) -> dict:
    visual = resolved.get("visual_identity") or {}
    overrides = raw.get("visual_overrides") or {}
    if overrides:
        visual = _merge_dict(visual, overrides)
    resolved["visual_identity"] = visual
    scene = resolved.get("scene_identity") or {}
    scene_overrides = raw.get("scene_overrides") or {}
    if scene_overrides:
        scene = _merge_dict(scene, scene_overrides)
    resolved["scene_identity"] = scene
    resolved["variant_traits"] = list(raw.get("variant_traits") or [])
    return resolved


def resolve_monster_spec(
    spec_id: str,
    monster_dir: Path = MONSTER_DIR,
    family_dir: Path = FAMILY_DIR,
    species_dir: Path = SPECIES_DIR,
) -> dict:
    spec_id = str(spec_id or "").strip()
    if not spec_id:
        raise RuntimeError("Monster spec ID is required")

    path = monster_dir / f"{spec_id}.json"
    if not path.exists():
        raise RuntimeError(f"Monster spec not found: {path}")

    raw = _read_json(path)
    if raw.get("monster_id") != spec_id:
        raise RuntimeError(f"Monster spec ID mismatch in {path}")

    contract = load_monster_contract(ROOT / "config" / "universal_monster_contract.json")
    family_path = family_profile_path(raw, family_dir)
    family = _read_json(family_path) if family_path else {}
    species_path = species_profile_path(raw, species_dir)
    species = _read_json(species_path) if species_path else {}

    resolved = _merge_dict(family, species)
    resolved = _merge_dict(resolved, raw)
    resolved = _apply_contract_defaults(resolved, contract)
    resolved = _apply_minimal_recipe(resolved, raw)

    taxonomy = family.get("taxonomy") or {}
    resolved["family"] = raw.get("family") or taxonomy.get("family") or raw.get("family_profile")
    resolved["size"] = raw.get("size") or taxonomy.get("default_size") or ""
    resolved["creature_type"] = raw.get("creature_type") or taxonomy.get("creature_type") or ""
    resolved["schema_version"] = int(raw.get("schema_version") or 1)
    resolved["identity_version"] = int(raw.get("identity_version") or family.get("identity_version") or 1)
    resolved["monster_contract"] = contract.get("contract_id")
    resolved["catalog"] = {
        "monster_file": path.relative_to(ROOT).as_posix()
        if ROOT in path.resolve().parents else str(path),
        "family_profile": family_path.relative_to(ROOT).as_posix()
        if family_path and ROOT in family_path.resolve().parents else None,
        "species_profile": species_path.relative_to(ROOT).as_posix()
        if species_path and ROOT in species_path.resolve().parents else None,
        "family_identity_version": family.get("identity_version"),
        "species_identity_version": species.get("identity_version"),
        "minimal_recipe": not bool(raw.get("visual_identity")),
    }
    return resolved


def minimal_recipe_errors(
    spec_id: str,
    monster_dir: Path = MONSTER_DIR,
    family_dir: Path = FAMILY_DIR,
    species_dir: Path = SPECIES_DIR,
) -> list[str]:
    path = monster_dir / f"{spec_id}.json"
    if not path.exists():
        return [f"Monster spec not found: {path}"]
    raw = _read_json(path)
    if int(raw.get("schema_version") or 1) < 3:
        return []
    contract = load_monster_contract(ROOT / "config" / "universal_monster_contract.json")
    errors = []
    for field in contract.get("minimal_recipe_required") or []:
        if not str(raw.get(field) or "").strip():
            errors.append(f"{spec_id}: minimal monster recipe missing {field}")
    family_path = family_profile_path(raw, family_dir)
    if not family_path:
        errors.append(f"{spec_id}: minimal monster recipe requires a valid family_profile")
    species_id = str(raw.get("species_profile") or "").strip()
    if species_id and not species_profile_path(raw, species_dir):
        errors.append(f"{spec_id}: species_profile {species_id!r} does not exist")
    for field in contract.get("recipe_forbidden_fields") or []:
        if field in raw:
            errors.append(f"{spec_id}: schema-v3+ monster recipe must not inline {field}")
    allowed = set(contract.get("minimal_recipe_required") or []) | set(
        contract.get("minimal_recipe_optional") or []
    )
    for field in sorted(set(raw) - allowed):
        errors.append(f"{spec_id}: schema-v3+ monster recipe has unsupported field {field}")
    return errors


def load_monster_for_page(
    page: dict,
    monster_dir: Path = MONSTER_DIR,
    family_dir: Path = FAMILY_DIR,
    species_dir: Path = SPECIES_DIR,
) -> dict | None:
    spec_id = str(page.get("monster_spec_id") or "").strip()
    if not spec_id:
        return None
    return resolve_monster_spec(spec_id, monster_dir, family_dir, species_dir)
