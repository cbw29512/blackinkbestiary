from __future__ import annotations

from pathlib import Path

try:
    from .environment_catalog import load_environment_contract, resolve_environment_profile
    from .environment_components import assemble_environment_palette
    from .quality_system import (
        coloring_page_directives,
        coloring_page_failures,
        environment_approval_checks,
        environment_directives,
    )
except ImportError:
    from environment_catalog import load_environment_contract, resolve_environment_profile
    from environment_components import assemble_environment_palette
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


def _required_object_rules(page: dict) -> list[str]:
    variant = page.get("environment_variant") or {}
    text = " ".join([
        str(page.get("moment") or ""),
        " ".join(str(item) for item in page.get("must_include") or []),
        str(variant.get("landmark") or ""),
        str(variant.get("interaction") or ""),
    ]).lower()
    rules = []
    if "wall torch" in text or "wall sconce" in text or "torch bracket" in text:
        rules.append(
            "Required wall-mounted light must visibly attach to the wall with a bracket, ring, plate, or niche; "
            "never draw it as a freestanding floor torch, post, or lamp."
        )
    if "tripwire" in text:
        rules.append(
            "Required tripwire must visibly cross the traversable path at believable ankle or shin height and "
            "visibly connect to the triggered hazard so cause-and-effect reads instantly."
        )
    if "pressure plate" in text:
        rules.append(
            "Required pressure plate must be visibly integrated into the walking surface and clearly associated "
            "with the hazard it activates."
        )
    if "pit" in text:
        rules.append(
            "Required pit must have a clear structural rim/opening and readable interior hazard without excessive tiny spikes."
        )
    return rules

def environment_prompt_sections(page: dict, root: Path) -> list[str]:
    profile = load_environment_for_page(page)
    variant = page.get("environment_variant") or {}
    identity = profile.get("resolved_identity") or {}
    palette = assemble_environment_palette(page, root)
    component_lines = [
        f"SELECTED {group.replace('_', ' ').upper()}: {item.get('text', '')}."
        for group, item in palette["components"].items()
    ]
    overlay_rules = [
        rule
        for overlay in palette["overlays"]
        for rule in overlay.get("directives") or []
    ]
    return [
        f"ENVIRONMENT PROFILE: {profile['name']}.",
        f"ENVIRONMENT SPATIAL TYPE: {identity.get('spatial_type', '')}.",
        f"ENVIRONMENT MATERIAL LANGUAGE: {identity.get('material_language', '')}.",
        _items("ENVIRONMENT IDENTITY MARKERS", identity.get("identity_markers")),
        f"ENVIRONMENT SPATIAL READ: {identity.get('spatial_read', '')}.",
        _items("UNIVERSAL ENVIRONMENT IDENTITY RULES", load_environment_contract().get("prompt_rules")),
        f"ENVIRONMENT ACCURACY: {profile['description']}",
        _items("ENVIRONMENT VISUAL CUES", profile.get("visual_cues")),
        _items("LARGE COLORABLE ENVIRONMENT FORMS", profile.get("colorable_forms")),
        _items("ENVIRONMENT ERRORS TO AVOID", profile.get("must_avoid")),
        _items("ENVIRONMENT ASSEMBLY CONTEXTS", palette.get("contexts")),
        *component_lines,
        _items("ACTIVE ENVIRONMENT OVERLAY RULES", overlay_rules),
        _items("REQUIRED OBJECT PHYSICAL RULES", _required_object_rules(page)),
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
    checks = [
        f"Environment matches profile: {profile['name']}",
        f"Spatial type reads without the monster: {identity.get('spatial_type', '')}",
        f"Material language is visible: {identity.get('material_language', '')}",
        f"At least one unmistakable location marker is visible: {', '.join(identity.get('identity_markers') or [])}",
        f"Spatial geometry reads correctly: {identity.get('spatial_read', '')}",
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
