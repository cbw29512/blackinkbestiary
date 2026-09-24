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

MODE_CONTACT_RULES = {
    "kicking": (
        "KICKING CONTACT LOCK: one support foot is visibly planted; the striking foot visibly contacts the target; "
        "the target is tipped, displaced, or reacting to impact. Do not put the target in the creature's hand."
    ),
    "wedged": (
        "WEDGED CONTACT LOCK: the body is visibly compressed between at least two architectural boundaries. "
        "Torso or limbs must touch both constraining surfaces so the creature cannot read as freely standing or posing."
    ),
    "attached-peeling": (
        "ATTACHED-PEELING LOCK: one continuous portion of the creature remains visibly attached overhead while the rest of the body peels away. "
        "Do not replace body attachment with hands, feet, chains, ropes, or an invented hanging limb."
    ),
    "hanging": (
        "HANGING CONTACT LOCK: the creature's canonical gripping anatomy visibly bears its weight from the overhead support. "
        "Do not invent extra hands, arms, hooks, ropes, or limbs to explain suspension."
    ),
    "ground-swarm": (
        "GROUND-SWARM CONTACT LOCK: individuals visibly emerge from the origin and contact the walking surface in one directional flow with broad white gaps."
    ),
    "coiled-contact": (
        "COILED-CONTACT LOCK: the body visibly rests against the support surface or object along multiple points; no unsupported floating segments."
    ),
    "web-supported": (
        "WEB-SUPPORTED LOCK: multiple canonical legs visibly contact tensioned web strands and the body sits where those strands support its weight."
    ),
    "descending": (
        "DESCENDING CONTACT LOCK: at least one weight-bearing foot is visibly planted on a stair tread while the body is shifted toward a lower tread. "
        "The pose must read as moving down the stair, not standing neutrally on level ground."
    ),
    "crawling": (
        "CRAWLING CONTACT LOCK: the subject is supported by the canonical contact points named by the page recipe and visibly advances across the surface. "
        "Do not replace crawling with an upright body, floating pose, or neutral still life."
    ),
    "feeding-swarm": (
        "FEEDING-SWARM CONTACT LOCK: several individuals visibly attach to or feed from the target while the rest cluster nearby at comparable scale. "
        "The target-contact points must be obvious; no giant leader or wallpaper-density swarm."
    ),
    "grounded": (
        "GROUNDED CONTACT LOCK: all visible weight-bearing feet or paws contact the named support surface. "
        "Body language must visibly express the page's required action rather than a neutral portrait pose."
    ),
    "crouched-dragging": (
        "CROUCHED-DRAGGING LOCK: the overhead boundary is visibly low enough to force a crouch; knees/torso compress under it while one hand or rope visibly drags the named object along the floor. "
        "The creature may not stand upright in a normal-height passage."
    ),
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
    mode = str(physicality.get("mode") or "").strip().lower()
    if can_fly and powered_airborne(mode):
        flight_rule = (
            "FLIGHT RULE: this page uses controlled natural flight. Flight capability never invents wings, arms, or a new body plan; "
            "use only the canonical locomotion anatomy already defined for the creature."
        )
    elif can_fly:
        flight_rule = (
            f"NON-FLIGHT POSE LOCK: although this creature can fly in other contexts, this page is explicitly {mode or 'supported'}, not airborne. "
            "Do not depict flight, spread invented wings, or add/alter limbs to imply flight. Preserve only the canonical body plan and the required support/contact."
        )
    else:
        flight_rule = (
            "FLIGHT RULE: this creature cannot fly. Keep it in a stable natural pose with clear support/contact; "
            "no jumping, falling, dropping, hovering, or midair freeze-frames."
        )
    mode_rule = MODE_CONTACT_RULES.get(mode, "")
    return [
        f"PHYSICAL STATE: {physicality.get('mode', '')}.",
        f"PHYSICAL SUPPORT / CONTACT: {physicality.get('support', '')}.",
        f"PHYSICAL MOTION / WEIGHT: {physicality.get('motion', '')}.",
        mode_rule,
        flight_rule,
        "STATIC COLORING RULE: prioritize readable anatomy and a stable natural pose over dramatic motion.",
    ]


def physicality_checklist(page: dict) -> list[str]:
    physicality = page.get("physicality") or {}
    can_fly = bool((page.get("locomotion") or {}).get("can_fly"))
    mode = str(physicality.get("mode") or "").strip().lower()
    mode_rule = MODE_CONTACT_RULES.get(mode, "")
    checks = [
        f"Physical state reads as: {physicality.get('mode', '')}",
        f"Support/contact is visible and believable: {physicality.get('support', '')}",
        f"Motion/weight reads correctly: {physicality.get('motion', '')}",
    ]
    if mode_rule:
        checks.append(f"Mode-specific contact geometry reads correctly: {mode_rule}")
    checks.extend([
        f"Controlled powered flight allowed by monster data: {can_fly}",
        "Pose is stable, natural, and easy to read in a static coloring page",
        "No jumping, falling, dropping, or accidental hovering",
    ])
    return checks
