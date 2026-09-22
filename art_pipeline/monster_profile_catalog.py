from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAMILY_DIR = ROOT / "data" / "monster_families"
IDENTITY_DIR = ROOT / "data" / "monster_identity_profiles"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load monster profile {path}: {exc}") from exc


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


def _family_path(profile_id: str, family_dir: Path) -> Path | None:
    if not profile_id:
        return None
    path = family_dir / f"{profile_id}.json"
    return path if path.exists() else None


def _identity_path(profile_id: str, identity_dir: Path, family_dir: Path) -> Path | None:
    if not profile_id:
        return None
    identity = identity_dir / f"{profile_id}.json"
    if identity.exists():
        return identity
    return _family_path(profile_id, family_dir)


def resolve_profile_layers(
    raw: dict,
    family_dir: Path = FAMILY_DIR,
    identity_dir: Path = IDENTITY_DIR,
) -> dict:
    requested_identity = str(raw.get("identity_profile") or "").strip()
    requested_family = str(raw.get("family_profile") or raw.get("family") or "").strip()
    identity_path = _identity_path(requested_identity, identity_dir, family_dir)
    identity = _read_json(identity_path) if identity_path else {}

    inherited_family = str(identity.get("extends_family") or "").strip()
    if requested_family and inherited_family and requested_family != inherited_family:
        raise RuntimeError(
            f"monster recipe family_profile {requested_family!r} conflicts with "
            f"identity profile parent {inherited_family!r}"
        )
    family_id = requested_family or inherited_family
    family_path = _family_path(family_id, family_dir)
    family = _read_json(family_path) if family_path else {}

    if requested_identity and not identity_path:
        raise RuntimeError(f"identity_profile {requested_identity!r} does not exist")
    if family_id and not family_path:
        raise RuntimeError(f"family_profile {family_id!r} does not exist")

    base = merge_dict(family, identity)
    return {
        "base": base,
        "family": family,
        "identity": identity,
        "family_id": family_id or None,
        "identity_id": requested_identity or None,
        "family_path": family_path,
        "identity_path": identity_path,
    }


def resolved_profile_errors(profile: dict) -> list[str]:
    visual = profile.get("visual_identity") or {}
    errors = []
    for field in (
        "core_identity",
        "silhouette",
        "head_features",
        "body_shape",
        "limb_structure",
        "surface",
        "must_keep",
        "must_avoid",
    ):
        if not visual.get(field):
            errors.append(f"resolved identity missing visual_identity.{field}")
    if not profile.get("accuracy_checks"):
        errors.append("resolved identity missing accuracy_checks")
    if not profile.get("known_failure_modes"):
        errors.append("resolved identity missing known_failure_modes")
    return errors
