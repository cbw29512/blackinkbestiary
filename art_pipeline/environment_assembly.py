from __future__ import annotations

import hashlib
from pathlib import Path

try:
    from .environment_catalog import load_environment_contract, resolve_environment_profile
    from .environment_component_catalog import (
        component_catalog_errors,
        infer_contexts,
        load_component_catalog,
        load_overlay_registry,
    )
except ImportError:
    from environment_catalog import load_environment_contract, resolve_environment_profile
    from environment_component_catalog import (
        component_catalog_errors,
        infer_contexts,
        load_component_catalog,
        load_overlay_registry,
    )

ROOT = Path(__file__).resolve().parents[1]


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
    offset = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
    return dict(eligible[(offset + max(order - 1, 0)) % len(eligible)])


def _chosen_groups(contract: dict, contexts: set[str], overlays: list[dict]) -> list[str]:
    budget = contract.get("assembly_budget") or {}
    biased = {group for overlay in overlays for group in overlay.get("component_bias") or []}
    accents = list(budget.get("accent_groups") or [])
    accents.sort(key=lambda group: (group not in biased, group))
    groups = list(budget.get("core_groups") or [])
    groups.extend(accents[: int(budget.get("selected_accents") or 2)])
    if "trap" in contexts or any(item["overlay_id"] == "trap_zone" for item in overlays):
        groups.extend(budget.get("conditional_groups") or [])
    groups.append(str(budget.get("story_group") or "interaction_patterns"))
    return list(dict.fromkeys(groups))


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
    contexts = infer_contexts(profile, catalog)
    overlays = infer_overlays(page, profile, root)
    key = "|".join([
        str(page.get("page_id") or ""),
        str(page.get("monster_spec_id") or ""),
        str(profile.get("environment_id") or ""),
    ])
    order = int(page.get("order") or 1)
    components = {}
    for group in _chosen_groups(contract, contexts, overlays):
        options = (catalog.get("groups") or {}).get(group) or []
        if options:
            components[group] = _pick(options, contexts, f"{key}|{group}", order)

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
