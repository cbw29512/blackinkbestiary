from __future__ import annotations

import json
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_FILE = ROOT / "data" / "environment_variation_families.json"
CONTRACT_FILE = ROOT / "config" / "universal_environment_contract.json"

LOGGER = logging.getLogger(__name__)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load environment engine JSON: %s", path)
        raise RuntimeError(f"Could not load environment engine JSON {path}: {exc}") from exc


def load_variation_registry(path: Path = REGISTRY_FILE) -> dict:
    payload = _read_json(path)
    if not isinstance(payload.get("families"), dict):
        raise RuntimeError("environment variation registry requires a families mapping")
    return payload


def load_variation_contract(path: Path = CONTRACT_FILE) -> dict:
    payload = _read_json(path)
    rules = payload.get("variation_depth")
    if not isinstance(rules, dict):
        raise RuntimeError("universal environment contract requires variation_depth")
    return payload


def family_variation_errors(
    family_id: str,
    payload: dict,
    contract: dict | None = None,
) -> list[str]:
    rules = (contract or load_variation_contract()).get("variation_depth") or {}
    required_pools = list(rules.get("required_pools") or [])
    try:
        minimum = int(rules.get("minimum_options_per_pool"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("variation_depth.minimum_options_per_pool must be an integer") from exc

    family = (payload.get("families") or {}).get(family_id)
    if not isinstance(family, dict):
        return [f"environment family {family_id!r} missing variation definition"]

    errors: list[str] = []
    for key in required_pools:
        values = family.get(key)
        if not isinstance(values, list):
            errors.append(f"{family_id}: {key} must be a list")
            continue
        clean = [str(item).strip() for item in values if str(item).strip()]
        if len(clean) < minimum:
            errors.append(
                f"{family_id}: {key} requires at least {minimum} useful options"
            )
    return errors


def resolve_family_variation(
    family_id: str,
    path: Path = REGISTRY_FILE,
    contract_path: Path = CONTRACT_FILE,
) -> dict:
    wanted = str(family_id or "").strip()
    if not wanted:
        raise RuntimeError("environment family id is required for variation resolution")

    payload = load_variation_registry(path)
    contract = load_variation_contract(contract_path)
    errors = family_variation_errors(wanted, payload, contract)
    if errors:
        raise RuntimeError("; ".join(errors))

    return dict(payload["families"][wanted])
