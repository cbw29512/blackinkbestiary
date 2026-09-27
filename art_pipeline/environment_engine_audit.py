from __future__ import annotations

import json
from pathlib import Path

try:
    from .environment_component_catalog import (
        component_catalog_errors,
        load_component_catalog,
        load_overlay_registry,
    )
    from .environment_catalog import resolve_environment_profile
    from .environment_spatial import spatial_envelope_errors
except ImportError:
    from environment_component_catalog import (
        component_catalog_errors,
        load_component_catalog,
        load_overlay_registry,
    )
    from environment_catalog import resolve_environment_profile
    from environment_spatial import spatial_envelope_errors


def _family_ids(root: Path) -> set[str]:
    ids = set()
    for path in sorted((root / "data" / "environment_families").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        family_id = str(payload.get("family_id") or "").strip()
        if family_id:
            ids.add(family_id)
    return ids


def audit_environment_engine(root: Path) -> dict:
    family_ids = _family_ids(root)
    component_dir = root / "data" / "environment_components"
    component_ids = {path.stem for path in component_dir.glob("*.json")}
    errors = []
    total_components = 0
    group_counts = {}

    for family_id in sorted(family_ids):
        errors.extend(component_catalog_errors(family_id, root))
        if family_id not in component_ids:
            continue
        catalog = load_component_catalog(family_id, root)
        counts = {
            group: len(items)
            for group, items in (catalog.get("groups") or {}).items()
        }
        group_counts[family_id] = counts
        total_components += sum(counts.values())

    for family_id in sorted(component_ids - family_ids):
        errors.append(f"component catalog has unknown environment family {family_id!r}")

    profile_count = 0
    for path in sorted((root / "data" / "environment_families").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for profile_id in (payload.get("profiles") or {}):
            profile_count += 1
            profile = resolve_environment_profile(
                profile_id,
                root / "data" / "environment_families",
            )
            errors.extend(
                f"{profile_id}: {error}" for error in spatial_envelope_errors(profile)
            )

    try:
        overlays = load_overlay_registry(root).get("overlays") or {}
    except RuntimeError as exc:
        errors.append(str(exc))
        overlays = {}
    required_roles = {
        "lair", "trap_zone", "ruin", "sacred", "military", "burial", "treasure",
        "fungal", "aquatic", "weathered", "settlement", "laboratory", "inhabited",
        "open_terrain", "forge", "library", "kitchen", "prison", "mine", "campsite",
        "village", "swamp", "desert", "mountain", "coastal", "throne_room", "nest",
    }
    missing_roles = sorted(required_roles - set(overlays))
    if missing_roles:
        errors.append("environment overlay registry missing required roles: " + ", ".join(missing_roles))
    for overlay_id, overlay in overlays.items():
        if not overlay.get("trigger_terms"):
            errors.append(f"environment overlay {overlay_id!r} requires trigger_terms")
        if len(overlay.get("directives") or []) < 2:
            errors.append(f"environment overlay {overlay_id!r} requires at least two directives")
        if not overlay.get("component_bias"):
            errors.append(f"environment overlay {overlay_id!r} requires component_bias")

    return {
        "pass": not errors,
        "environment_families": len(family_ids),
        "component_catalogs": len(component_ids),
        "total_components": total_components,
        "overlay_count": len(overlays),
        "profile_count": profile_count,
        "group_counts": group_counts,
        "errors": errors,
    }
