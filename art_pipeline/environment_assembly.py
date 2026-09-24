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
    """Select a small, deterministic set of environment-owned roles.

    Explicit page roles are authoritative. Inferred roles are ranked by the
    specificity of the matched trigger instead of registry insertion order.
    This prevents broad roles such as inhabited/lair from crowding out a more
    specific role such as laboratory, prison, nest, or forge.
    """
    registry = load_overlay_registry(root)
    overlays = registry["overlays"]
    variant = page.get("environment_variant") or {}
    haystack = " ".join([
        str(profile.get("environment_id") or ""),
        str(profile.get("name") or ""),
        str(page.get("moment") or ""),
        str(page.get("archetype") or ""),
        str(variant.get("landmark") or ""),
        str(variant.get("framing") or ""),
        str(variant.get("interaction") or ""),
    ]).lower()

    selected: list[dict] = []
    seen: set[str] = set()

    explicit = [
        *(str(item) for item in page.get("environment_roles") or []),
        *(str(item) for item in page.get("environment_overlays") or []),
    ]
    for overlay_id in explicit:
        overlay_id = overlay_id.strip()
        if overlay_id in overlays and overlay_id not in seen:
            selected.append({"overlay_id": overlay_id, **overlays[overlay_id]})
            seen.add(overlay_id)
            if len(selected) == 3:
                return selected

    inferred = []
    for overlay_id, overlay in overlays.items():
        if overlay_id in seen:
            continue
        matches = [
            str(term).lower()
            for term in overlay.get("trigger_terms") or []
            if str(term).strip() and str(term).lower() in haystack
        ]
        if matches:
            # Longer phrases are more specific. A role with fewer trigger terms
            # wins the final tie so generic catch-all roles do not dominate.
            score = (max(len(term) for term in matches), -len(overlay.get("trigger_terms") or []), overlay_id)
            inferred.append((score, overlay_id, overlay))

    for _, overlay_id, overlay in sorted(inferred, reverse=True):
        selected.append({"overlay_id": overlay_id, **overlay})
        seen.add(overlay_id)
        if len(selected) == 3:
            break
    return selected


def _compatibility_score(item: dict, contexts: set[str]) -> tuple[int, int, int, int] | None:
    tags = {str(x).lower() for x in item.get("contexts") or [] if str(x).strip()}
    if not tags:
        return None
    if "universal" in tags:
        # Universal components are safe fallbacks, but an exact specific match
        # should beat them whenever one exists.
        return (0, 0, 0, -len(tags))

    overlap = tags.intersection(contexts)
    if not overlap:
        return None
    foreign = tags.difference(contexts)
    exact = 1 if not foreign else 0
    return (exact, len(overlap), -len(foreign), -len(tags))


def _pick(items: list[dict], contexts: set[str], key: str, order: int) -> dict:
    ranked = []
    for item in items:
        score = _compatibility_score(item, contexts)
        if score is not None:
            ranked.append((score, item))
    if not ranked:
        ranked = [((0, 0, -999, 0), item) for item in items]

    best_score = max(score for score, _ in ranked)
    eligible = [item for score, item in ranked if score == best_score]
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
    # Background selection is environment-owned. Monster identity must not influence
    # which cave wall, reef shelf, field landmark, laboratory fixture, etc. is chosen.
    key = "|".join([
        str(page.get("page_id") or ""),
        str(profile.get("environment_id") or ""),
        str(page.get("environment_seed") or page.get("order") or 1),
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
