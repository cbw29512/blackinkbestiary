from __future__ import annotations

from pathlib import Path

try:
    from .environment_brief import build_room_brief
    from .environment_catalog import load_environment_contract, resolve_environment_profile
    from .environment_components import assemble_environment_palette
    from .environment_spatial import resolve_spatial_envelope
    from .quality_system import (
        coloring_page_directives,
        coloring_page_failures,
        environment_approval_checks,
        environment_directives,
    )
except ImportError:
    from environment_brief import build_room_brief
    from environment_catalog import load_environment_contract, resolve_environment_profile
    from environment_components import assemble_environment_palette
    from environment_spatial import resolve_spatial_envelope
    from quality_system import (
        coloring_page_directives,
        coloring_page_failures,
        environment_approval_checks,
        environment_directives,
    )


def _items(label: str, values) -> str:
    clean = [str(item).strip() for item in (values or []) if str(item).strip()]
    return f"{label}: " + "; ".join(clean) + "." if clean else ""


def load_environment_for_page(page: dict) -> dict:
    return resolve_environment_profile(page.get("environment_profile_id"))


def environment_prompt_sections(page: dict, root: Path) -> list[str]:
    profile = load_environment_for_page(page)
    variant = page.get("environment_variant") or {}
    identity = profile.get("resolved_identity") or {}
    palette = assemble_environment_palette(page, root)
    envelope = resolve_spatial_envelope(profile)
    room = build_room_brief(page, root)
    component_lines = [
        f"ROOM COMPONENT — {group.replace('_', ' ')}: {item.get('text', '')}."
        for group, item in palette["components"].items()
    ]
    overlay_rules = [
        rule
        for overlay in palette["overlays"]
        for rule in overlay.get("directives") or []
    ]
    return [
        f"ROOM BRIEF — AUTHORITATIVE: {room['brief']}",
        _items("ROOM PROOF CUES", room.get("proof_cues")),
        _items("ROOM DRIFT FAILURES", room.get("drift_failures")),
        _items("ROOM COLORING FORMS", profile.get("colorable_forms")),
        _items("ROOM PROFILE ERRORS", profile.get("must_avoid")),
        *component_lines,
        _items("ACTIVE ENVIRONMENT OVERLAY RULES", overlay_rules),
        _items("FAMILY ENVIRONMENT QUALITY RULES", palette.get("family_quality_rules")),
        (
            "ENVIRONMENT PALETTE RULE: these selected components are a compatible design palette, "
            "not permission to clutter the page. Use only the few forms needed for a premium, readable, "
            "highly colorable setting. Explicit page landmark, framing, and interaction remain authoritative."
        ),
        f"UNIQUE BACKGROUND LANDMARK: {variant.get('landmark', '')}.",
        f"UNIQUE BACKGROUND FRAMING: {variant.get('framing', '')}.",
        f"MONSTER / ENVIRONMENT INTERACTION: {variant.get('interaction', '')}.",
        _items("GLOBAL ENVIRONMENT STANDARD", environment_directives(root)),
        _items("COLORING-PAGE SCALE STANDARD", coloring_page_directives(root)),
    ]


def environment_checklist(page: dict, root: Path) -> list[str]:
    profile = load_environment_for_page(page)
    variant = page.get("environment_variant") or {}
    identity = profile.get("resolved_identity") or {}
    envelope = resolve_spatial_envelope(profile)
    checks = [
        f"Environment matches profile: {profile['name']}",
        f"Spatial type reads without the monster: {identity.get('spatial_type', '')}",
        f"Material language is visible: {identity.get('material_language', '')}",
        f"At least one unmistakable location marker is visible: {', '.join(identity.get('identity_markers') or [])}",
        f"Spatial geometry reads correctly: {identity.get('spatial_read', '')}",
        f"Space envelope matches: {envelope['envelope_id']} — {envelope.get('plan_shape', '')}",
        f"Space proportions read correctly: {envelope.get('proportions', '')}",
        f"Space overhead/ceiling reads correctly: {envelope.get('ceiling', '')}",
        f"Space does not drift into: {', '.join(envelope.get('must_not_drift') or [])}",
        f"Unique landmark is visible: {variant.get('landmark', '')}",
        f"Framing differs from repeated generic backgrounds: {variant.get('framing', '')}",
        f"Monster/environment interaction reads clearly: {variant.get('interaction', '')}",
        "Environment geometry differs meaningfully from nearby pages before extra props are added",
        "Monster is large, centered or near-centered, and the dominant focal shape",
        "Major environmental objects are large and comfortable to color but visually secondary to the monster",
        "Monster leaves enough surrounding page area for the habitat to read",
        "Background depth comes from a few large forms, not micro-detail",
    ]
    checks.extend(f"Environment check: {item}" for item in environment_approval_checks(root))
    checks.extend(f"Colorability failure to reject: {item}" for item in coloring_page_failures(root))
    return checks
