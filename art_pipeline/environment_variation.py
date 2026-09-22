from __future__ import annotations

import json
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_FILE = ROOT / "data" / "environment_variation_families.json"

LOGGER = logging.getLogger(__name__)

REQUIRED_POOLS = (
    "geometry_pool",
    "landmark_pool",
    "prop_pool",
    "interaction_pool",
    "anti_repetition_rules",
)
MIN_POOL_SIZE = 4


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load environment variation registry: %s", path)
        raise RuntimeError(
            f"Could not load environment variation registry {path}: {exc}"
        ) from exc


def load_variation_registry(path: Path = REGISTRY_FILE) -> dict:
    payload = _read_json(path)
    if not isinstance(payload.get("families"), dict):
        raise RuntimeError("environment variation registry requires a families mapping")
    return payload


def family_variation_errors(family_id: str, payload: dict) -> list[str]:
    family = (payload.get("families") or {}).get(family_id)
    if not isinstance(family, dict):
        return [f"environment family {family_id!r} missing variation definition"]

    errors: list[str] = []
    for key in REQUIRED_POOLS:
        values = family.get(key)
        if not isinstance(values, list):
            errors.append(f"{family_id}: {key} must be a list")
            continue
        clean = [str(item).strip() for item in values if str(item).strip()]
        if len(clean) < MIN_POOL_SIZE:
            errors.append(
                f"{family_id}: {key} requires at least {MIN_POOL_SIZE} useful options"
            )
    return errors


def resolve_family_variation(
    family_id: str,
    path: Path = REGISTRY_FILE,
) -> dict:
    wanted = str(family_id or "").strip()
    if not wanted:
        raise RuntimeError("environment family id is required for variation resolution")

    payload = load_variation_registry(path)
    errors = family_variation_errors(wanted, payload)
    if errors:
        raise RuntimeError("; ".join(errors))

    return dict(payload["families"][wanted])
