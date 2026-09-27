from __future__ import annotations

import json
import logging
from pathlib import Path

try:
    from .environment_catalog import load_environment_contract
except ImportError:
    from environment_catalog import load_environment_contract

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load environment component data: %s", path)
        raise RuntimeError(f"Could not load environment component data {path}: {exc}") from exc


def load_component_catalog(family_id: str, root: Path = ROOT) -> dict:
    path = root / "data" / "environment_components" / f"{family_id}.json"
    payload = _read_json(path)
    if payload.get("family_id") != family_id:
        raise RuntimeError(f"Environment component family mismatch in {path}")
    return payload


def load_overlay_registry(root: Path = ROOT) -> dict:
    payload = _read_json(root / "data" / "environment_overlays.json")
    if not isinstance(payload.get("overlays"), dict):
        raise RuntimeError("environment overlay registry requires overlays")
    return payload


def infer_contexts(profile: dict, catalog: dict) -> set[str]:
    text = " ".join([
        str(profile.get("environment_id") or ""),
        str(profile.get("name") or ""),
        str(profile.get("description") or ""),
    ]).lower()
    contexts = {"universal", str(profile.get("environment_family") or "").lower()}
    for rule in catalog.get("context_rules") or []:
        terms = [str(item).lower() for item in rule.get("terms") or []]
        if any(term and term in text for term in terms):
            contexts.update(str(item).lower() for item in rule.get("add") or [])

    # Component contexts are also a reusable vocabulary. If a concrete tag is
    # literally named by the environment profile (spiral stair -> stair,
    # limestone cave -> limestone/cave, webbed hall -> webbed/hall), preserve
    # that specificity instead of collapsing everything to broad family tags.
    known_tags = {
        str(tag).lower()
        for items in (catalog.get("groups") or {}).values()
        for item in (items or [])
        for tag in (item.get("contexts") or [])
        if str(tag).strip()
    }
    for tag in known_tags:
        if tag not in {"universal", str(profile.get("environment_family") or "").lower()} and tag in text:
            contexts.add(tag)
    return contexts


def component_catalog_errors(family_id: str, root: Path = ROOT) -> list[str]:
    contract = load_environment_contract(root / "config" / "universal_environment_contract.json")
    rules = contract.get("component_engine") or {}
    required = list(rules.get("required_groups") or [])
    minimum = int(rules.get("minimum_options_per_group") or 1)
    try:
        catalog = load_component_catalog(family_id, root)
    except RuntimeError as exc:
        return [str(exc)]

    errors = []
    groups = catalog.get("groups") or {}
    for group in required:
        values = groups.get(group)
        if not isinstance(values, list) or len(values) < minimum:
            errors.append(f"{family_id}: {group} requires at least {minimum} options")
            continue
        for item in values:
            if not isinstance(item, dict) or not str(item.get("text") or "").strip():
                errors.append(f"{family_id}: {group} contains invalid component")
                break
            if not isinstance(item.get("contexts"), list) or not item["contexts"]:
                errors.append(f"{family_id}: {group} component missing contexts")
                break
    return errors
