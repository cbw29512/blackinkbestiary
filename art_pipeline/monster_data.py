from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONSTER_DIR = ROOT / "data" / "monsters"
FAMILY_DIR = ROOT / "data" / "monster_families"
VARIANT_DIR = ROOT / "data" / "monster_variants"
CONTRACT_FILE = ROOT / "config" / "universal_monster_contract.json"


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load creature catalog file {path}: {exc}") from exc


def merge_unique(base, override):
    result = []
    for item in list(base or []) + list(override or []):
        if item not in result:
            result.append(item)
    return result


def merge_dict(base: dict, override: dict | None) -> dict:
    merged = deepcopy(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dict(merged[key], value)
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = merge_unique(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def family_profile_path(spec: dict, family_dir: Path = FAMILY_DIR) -> Path | None:
    profile_id = str(spec.get("family_profile") or "").strip()
    if not profile_id:
        return None
    path = family_dir / f"{profile_id}.json"
    return path if path.exists() else None


def variant_profile_path(spec: dict, variant_dir: Path = VARIANT_DIR) -> Path | None:
    variant_id = str(spec.get("variant_profile") or "").strip()
    if not variant_id:
        return None
    path = variant_dir / f"{variant_id}.json"
    return path if path.exists() else None


def apply_contract_defaults(resolved: dict, contract: dict) -> dict:
    defaults = contract.get("defaults") or {}
    resolved["visual_identity"] = merge_dict(
        defaults.get("visual_identity") or {},
        resolved.get("visual_identity") or {},
    )
    resolved["default_habitats"] = merge_unique(
        defaults.get("default_habitats"),
        resolved.get("default_habitats"),
    )
    resolved["locomotion"] = merge_dict(
        defaults.get("locomotion") or {},
        resolved.get("locomotion") or {},
    )
    resolved["scene_identity"] = merge_dict(
        defaults.get("scene_identity") or {},
        resolved.get("scene_identity") or {},
    )
    return resolved


def apply_recipe_overrides(resolved: dict, raw: dict) -> dict:
    visual = resolved.get("visual_identity") or {}
    if raw.get("visual_overrides"):
        visual = merge_dict(visual, raw["visual_overrides"])
    resolved["visual_identity"] = visual
    scene = resolved.get("scene_identity") or {}
    if raw.get("scene_overrides"):
        scene = merge_dict(scene, raw["scene_overrides"])
    resolved["scene_identity"] = scene
    resolved["variant_traits"] = list(raw.get("variant_traits") or [])
    return resolved
