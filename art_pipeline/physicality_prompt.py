from __future__ import annotations

POWERED_AIR_MODES = {
    "flying",
    "flying-swarm",
    "hovering",
    "gliding",
    "levitating",
    "magical-flight",
}


def powered_airborne(mode: str) -> bool:
    return str(mode or "").strip().lower() in POWERED_AIR_MODES


def locomotion_errors(page: dict) -> list[str]:
    mode = str((page.get("physicality") or {}).get("mode") or "").strip().lower()
    can_fly = bool((page.get("locomotion") or {}).get("can_fly"))
    if powered_airborne(mode) and not can_fly:
        return [f"{page.get('page_id')}: non-flying creature cannot use {mode!r}"]
    return []


def physicality_sections(page: dict) -> list[str]:
    physicality = page.get("physicality") or {}
    can_fly = bool((page.get("locomotion") or {}).get("can_fly"))
    flight_rule = (
        "FLIGHT RULE: powered airborne poses are allowed for this creature, but wing/body motion must explain the flight."
        if can_fly
        else "FLIGHT RULE: this creature cannot fly. Keep it visibly supported unless it is clearly jumping or falling with an explicit source and trajectory."
    )
    return [
        f"PHYSICAL STATE: {physicality.get('mode', '')}.",
        f"PHYSICAL SUPPORT / CONTACT: {physicality.get('support', '')}.",
        f"PHYSICAL MOTION / WEIGHT: {physicality.get('motion', '')}.",
        flight_rule,
        "GROUNDING RULE: never show a neutral standing pose suspended in empty air.",
    ]


def physicality_checklist(page: dict) -> list[str]:
    physicality = page.get("physicality") or {}
    can_fly = bool((page.get("locomotion") or {}).get("can_fly"))
    return [
        f"Physical state reads as: {physicality.get('mode', '')}",
        f"Support/contact is visible and believable: {physicality.get('support', '')}",
        f"Motion/weight reads correctly: {physicality.get('motion', '')}",
        f"Powered flight allowed by monster data: {can_fly}",
        "No accidental hovering or static standing pose in midair",
    ]
