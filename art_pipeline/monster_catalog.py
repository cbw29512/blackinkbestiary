from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONSTER_DIR = ROOT / "data" / "monsters"
FAMILY_DIR = ROOT / "data" / "monster_families"


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


def _merge_dict(base: dict, override: dict) -> dict:
    merged = dict(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = _merge_unique(merged[key], value)
        else:
            merged[key] = value
    return merged


def family_profile_path(spec: dict, family_dir: Path = FAMILY_DIR) -> Path | None:
    profile_id = str(spec.get("family_profile") or spec.get("family") or "").strip()
    if not profile_id:
        return None
    path = family_dir / f"{profile_id}.json"
    return path if path.exists() else None


def resolve_monster_spec(
    spec_id: str,
    monster_dir: Path = MONSTER_DIR,
    family_dir: Path = FAMILY_DIR,
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

    family_path = family_profile_path(raw, family_dir)
    family = _read_json(family_path) if family_path else {}
    resolved = _merge_dict(family, raw)
    resolved["schema_version"] = int(raw.get("schema_version") or 1)
    resolved["identity_version"] = int(raw.get("identity_version") or 1)
    resolved["catalog"] = {
        "monster_file": path.relative_to(ROOT).as_posix()
        if ROOT in path.resolve().parents else str(path),
        "family_profile": family_path.relative_to(ROOT).as_posix()
        if family_path and ROOT in family_path.resolve().parents else None,
        "family_identity_version": family.get("identity_version"),
    }
    return resolved


def load_monster_for_page(
    page: dict,
    monster_dir: Path = MONSTER_DIR,
    family_dir: Path = FAMILY_DIR,
) -> dict | None:
    spec_id = str(page.get("monster_spec_id") or "").strip()
    if not spec_id:
        return None
    return resolve_monster_spec(spec_id, monster_dir, family_dir)
