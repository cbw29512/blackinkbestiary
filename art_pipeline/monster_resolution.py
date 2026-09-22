from __future__ import annotations

try:
    from .monster_profile_catalog import merge_dict, merge_unique
except ImportError:
    from monster_profile_catalog import merge_dict, merge_unique


def apply_defaults(resolved: dict, contract: dict) -> dict:
    defaults = contract.get("defaults") or {}
    for key in ("visual_identity", "locomotion", "scene_identity", "render_identity", "anatomy"):
        resolved[key] = merge_dict(defaults.get(key) or {}, resolved.get(key) or {})
    resolved["default_habitats"] = merge_unique(
        defaults.get("default_habitats"),
        resolved.get("default_habitats"),
    )
    return resolved


def apply_recipe(resolved: dict, raw: dict) -> dict:
    mapping = {
        "visual_overrides": "visual_identity",
        "scene_overrides": "scene_identity",
        "render_overrides": "render_identity",
        "anatomy_overrides": "anatomy",
    }
    for source, target in mapping.items():
        if raw.get(source):
            resolved[target] = merge_dict(resolved.get(target) or {}, raw[source])
    resolved["variant_traits"] = list(raw.get("variant_traits") or [])
    return resolved


def decorate_resolved(resolved: dict, raw: dict, layers: dict, contract: dict) -> dict:
    taxonomy = resolved.get("taxonomy") or {}
    resolved["family"] = (
        raw.get("family")
        or taxonomy.get("family")
        or layers["family_id"]
        or layers["identity_id"]
        or ""
    )
    resolved["size"] = raw.get("size") or taxonomy.get("default_size") or ""
    resolved["creature_type"] = raw.get("creature_type") or taxonomy.get("creature_type") or ""
    resolved["schema_version"] = int(raw.get("schema_version") or 1)
    resolved["identity_version"] = int(
        raw.get("identity_version")
        or layers["identity"].get("identity_version")
        or layers["family"].get("identity_version")
        or 1
    )
    resolved["monster_contract"] = contract.get("contract_id")
    return resolved
