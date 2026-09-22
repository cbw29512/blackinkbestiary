from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_DIR = ROOT / "data" / "environment_families"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load environment catalog file {path}: {exc}") from exc


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
