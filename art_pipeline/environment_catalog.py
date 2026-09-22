from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_DIR = ROOT / "data" / "environment_families"
CONTRACT_FILE = ROOT / "config" / "universal_environment_contract.json"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load environment catalog file {path}: {exc}") from exc


def load_environment_contract(path: Path = CONTRACT_FILE) -> dict:
    return _read_json(path)


def _resolved_identity(profile: dict) -> dict:
    explicit = profile.get("identity") or {}
    cues = [str(item).strip() for item in (profile.get("visual_cues") or []) if str(item).strip()]
    return {
        "spatial_type": str(explicit.get("spatial_type") or profile.get("name") or "").strip(),
        "material_language": str(explicit.get("material_language") or profile.get("description") or "").strip(),
        "identity_markers": list(explicit.get("identity_markers") or cues[:3]),
        "spatial_read": str(explicit.get("spatial_read") or (cues[0] if cues else profile.get("description") or "")).strip(),
    }


def environment_identity_errors(profile: dict) -> list[str]:
    identity = profile.get("resolved_identity") or _resolved_identity(profile)
    errors = []
    for field in ("spatial_type", "material_language", "spatial_read"):
        if not str(identity.get(field) or "").strip():
            errors.append(f"environment identity missing {field}")
    if not identity.get("identity_markers"):
        errors.append("environment identity missing identity_markers")
    return errors


def resolve_environment_profile(
    profile_id: str,
    environment_dir: Path = ENVIRONMENT_DIR,
) -> dict:
    wanted = str(profile_id or "").strip()
    if not wanted:
        raise RuntimeError("environment_profile_id is required")

    for path in sorted(environment_dir.glob("*.json")):
        family = _read_json(path)
        profiles = family.get("profiles") or {}
        if wanted not in profiles:
            continue
        profile = dict(profiles[wanted])
        profile["environment_id"] = wanted
        profile["environment_family"] = family.get("family_id")
        profile["environment_family_name"] = family.get("display_name")
        profile["resolved_identity"] = _resolved_identity(profile)
        profile["catalog_file"] = (
            path.relative_to(ROOT).as_posix()
            if ROOT in path.resolve().parents
            else str(path)
        )
        return profile
    raise RuntimeError(f"Environment profile not found: {wanted}")


def environment_fingerprint(page: dict) -> str:
    variant = page.get("environment_variant") or {}
    parts = [
        str(page.get("environment_profile_id") or "").strip().lower(),
        str(variant.get("landmark") or "").strip().lower(),
        str(variant.get("framing") or "").strip().lower(),
        str(variant.get("interaction") or "").strip().lower(),
    ]
    return "|".join(" ".join(part.split()) for part in parts)
