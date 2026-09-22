from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

try:
    from .environment_catalog import load_environment_contract, resolve_environment_profile
except ImportError:
    from environment_catalog import load_environment_contract, resolve_environment_profile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_DIR = ROOT / "data" / "environment_components"
OVERLAY_FILE = ROOT / "data" / "environment_overlays.json"
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


def infer_overlays(page: dict, profile: dict, root: Path = ROOT) -> list[dict]:
    registry = load_overlay_registry(root)
    variant = page.get("environment_variant") or {}
    haystack = " ".join([
        str(profile.get("environment_id") or ""),
        str(profile.get("name") or ""),
        str(page.get("moment") or ""),
        str(variant.get("landmark") or ""),
        str(variant.get("framing") or ""),
        str(variant.get("interaction") or ""),
        " ".join(str(item) for item in page.get("environment_overlays") or []),
    ]).lower()
    matches = []
    for overlay_id, overlay in registry["overlays"].items():
        terms = [str(item).lower() for item in overlay.get("trigger_terms") or []]
        if any(term and term in haystack for term in terms):
            matches.append({"overlay_id": overlay_id, **overlay})
    return matches[:2]


def _pick(items: list[dict], contexts: set[str], key: str, order: int) -> dict:
    eligible = [
        item for item in items
        if "universal" in {str(x).lower() for x in item.get("contexts") or []}
        or contexts.intersection(str(x).lower() for x in item.get("contexts") or [])
    ] or list(items)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    offset = int(digest[:8], 16)
    return dict(eligible[(offset + max(order - 1, 0)) % len(eligible)])


def assemble_environment_palette(page: dict, root: Path = ROOT) -> dict:
    profile = resolve_environment_profile(
        page.get("environment_profile_id"),
        root / "data" / "environment_families",
    )
    family_id = profile["environment_family"]
    catalog = load_component_catalog(family_id, root)
    errors = component_catalog_errors(family_id, root)
    if errors:
        raise RuntimeError("; ".join(errors))

    contract = load_environment_contract(root / "config" / "universal_environment_contract.json")
    budget = contract.get("assembly_budget") or {}
    contexts = infer_contexts(profile, catalog)
    overlays = infer_overlays(page, profile, root)
    biased = {group for overlay in overlays for group in overlay.get("component_bias") or []}
    accent_groups = list(budget.get("accent_groups") or [])
    accent_groups.sort(key=lambda group: (group not in biased, group))
    chosen_groups = list(budget.get("core_groups") or [])
    chosen_groups.extend(accent_groups[: int(budget.get("selected_accents") or 2)])
    if "trap" in contexts or any(x["overlay_id"] == "trap_zone" for x in overlays):
        chosen_groups.extend(budget.get("conditional_groups") or [])
    chosen_groups.append(str(budget.get("story_group") or "interaction_patterns"))

    order = int(page.get("order") or 1)
    page_key = "|".join([
        str(page.get("page_id") or ""),
        str(page.get("monster_spec_id") or ""),
        str(profile.get("environment_id") or ""),
    ])
    components = {}
    for group in dict.fromkeys(chosen_groups):
        options = (catalog.get("groups") or {}).get(group) or []
        if options:
            components[group] = _pick(options, contexts, f"{page_key}|{group}", order)

    return {
        "family_id": family_id,
        "profile_id": profile["environment_id"],
        "contexts": sorted(contexts),
        "overlays": overlays,
        "components": components,
        "family_quality_rules": list(catalog.get("family_quality_rules") or []),
    }


def assembly_fingerprint(page: dict, root: Path = ROOT) -> str:
    palette = assemble_environment_palette(page, root)
    values = [palette["profile_id"]]
    values.extend(item.get("id", "") for item in palette["components"].values())
    values.extend(item["overlay_id"] for item in palette["overlays"])
    return "|".join(values)
