try:
    from .physicality_modes import mode_prompt_sections, mode_review_checks
except ImportError:
    from physicality_modes import mode_prompt_sections, mode_review_checks

from __future__ import annotations

POWERED_AIR_MODES = {
    "flying",
    "flying-swarm",
    "hovering",
    "gliding",
    "levitating",
    "magical-flight",
}
UNSTABLE_COLORING_MODES = {
    "falling",
    "jumping",
    "leaping",
    "dropping",
    "midair",
}


def powered_airborne(mode: str) -> bool:
    return str(mode or "").strip().lower() in POWERED_AIR_MODES


def locomotion_errors(page: dict) -> list[str]:
    mode = str((page.get("physicality") or {}).get("mode") or "").strip().lower()
    can_fly = bool((page.get("locomotion") or {}).get("can_fly"))
    errors = []
    if mode in UNSTABLE_COLORING_MODES:
        errors.append(
            f"{page.get('page_id')}: unstable coloring pose {mode!r} is not allowed"
        )
    if powered_airborne(mode) and not can_fly:
        errors.append(f"{page.get('page_id')}: non-flying creature cannot use {mode!r}")
    return errors


def physicality_sections(page: dict) -> list[str]:
    physicality = page.get("physicality") or {}
    can_fly = bool((page.get("locomotion") or {}).get("can_fly"))
    flight_rule = (
        "FLIGHT RULE: this creature may use controlled natural flight, but avoid diving, falling, leaping, or chaotic midair freeze-frames."
        if can_fly
        else "FLIGHT RULE: this creature cannot fly. Keep it in a stable natural pose with clear support/contact; no jumping, falling, dropping, hovering, or midair freeze-frames."
    )
    return [
        f"PHYSICAL STATE: {physicality.get('mode', '')}.",
        *mode_prompt_sections(page),
        f"PHYSICAL SUPPORT / CONTACT: {physicality.get('support', '')}.",
        f"PHYSICAL MOTION / WEIGHT: {physicality.get('motion', '')}.",
        flight_rule,
        "STATIC COLORING RULE: prioritize readable anatomy and a stable natural pose over dramatic motion.",
    ]


def physicality_checklist(page: dict) -> list[str]:
    physicality = page.get("physicality") or {}
    can_fly = bool((page.get("locomotion") or {}).get("can_fly"))
    return [
        f"Physical state reads as: {physicality.get('mode', '')}",
        *mode_review_checks(page),
        f"Support/contact is visible and believable: {physicality.get('support', '')}",
        f"Motion/weight reads correctly: {physicality.get('motion', '')}",
        f"Controlled powered flight allowed by monster data: {can_fly}",
        "Pose is stable, natural, and easy to read in a static coloring page",
        "No jumping, falling, dropping, or accidental hovering",
    ]
