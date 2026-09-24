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
    "amorphous-contact": (
        "AMORPHOUS-CONTACT LOCK: the continuous body visibly deforms against the named support surface along a broad contact edge. "
        "Ripples, compression, or spread must originate at that contact; the mass may not hover or stand on invented limbs."
    ),
    "anchored": (
        "ANCHORED LOCK: the main body/base remains visibly planted at one fixed support area while tendrils, arms, or other canonical extensions move away from it. "
        "The anchor point must stay obvious and weight-bearing."
    ),
    "architectural-attachment": (
        "ARCHITECTURAL-ATTACHMENT LOCK: the creature/object remains visibly hinged, framed, embedded, bolted, rooted, or otherwise continuous with the named architecture. "
        "Living features emerge from that attached body; do not detach the subject into free space."
    ),
    "burrowing": (
        "BURROWING LOCK: a substantial portion of the body remains visibly inside or beneath the ground mass while soil/earth overlaps the body boundary and marks a readable travel path. "
        "Do not show the creature simply running or floating above intact ground."
    ),
    "bursting-from-ground": (
        "GROUND-BURST LOCK: the lower body remains visibly inside the fresh breach while displaced earth/stone radiates from that same opening and the upper body emerges through it. "
        "The breach must be the unmistakable source of motion."
    ),
    "ceiling-cling": (
        "CEILING-CLING LOCK: multiple canonical contact points visibly grip the overhead surface and the body stays close to that plane. "
        "Do not leave a gap that makes the subject look airborne or hanging from invented supports."
    ),
    "climbing-ooze": (
        "CLIMBING-OOZE LOCK: one continuous ooze mass visibly adheres to the climbed surface at multiple broad contact areas and deforms over/through its geometry. "
        "No feet, hands, unsupported floating lobes, or detached pieces unless the page explicitly requires a split body."
    ),
    "coiled-support": (
        "COILED-SUPPORT LOCK: multiple coils visibly wrap, press against, or rest on the named support so the support carries the body's weight. "
        "Coils may not float beside the object without contact."
    ),
    "crawling-emergence": (
        "CRAWLING-EMERGENCE LOCK: the body visibly contacts the floor/rubble while part of it still passes through or around the origin opening/cover. "
        "The leading end advances away from that origin with a clear emergence path."
    ),
    "elevated-standing": (
        "ELEVATED-STANDING LOCK: all visible weight-bearing feet are planted on the top surface of the named elevated support. "
        "Show the support top and foot contact clearly; no hovering above it or standing beside it."
    ),
    "embedded-rising": (
        "EMBEDDED-RISING LOCK: the lower body remains visibly buried/embedded in the named material while the upper body rises out of it. "
        "The material must overlap the body at the emergence boundary so the subject cannot read as standing on top."
    ),
    "flying-swarm": (
        "FLYING-SWARM LOCK: the group follows one readable airborne flow from a visible origin or through a clear route, with members at comparable scale and broad white gaps. "
        "No giant leader, random wallpaper scatter, or ambiguous source direction."
    ),
    "grounded-feeding": (
        "GROUNDED-FEEDING LOCK: canonical weight-bearing limbs visibly contact the ground/support while the actual feeding anatomy visibly contacts the target material. "
        "Standing near or merely looking at the food/metal/target is not feeding."
    ),
    "magical-flight": (
        "MAGICAL-FLIGHT LOCK: unsupported flight is intentional and clearly directional, with body/object orientation matching a visible path around or toward the named landmark. "
        "Do not invent wings, limbs, ropes, or supports to explain magical flight."
    ),
    "object-supported": (
        "OBJECT-SUPPORTED LOCK: the disguised/animated object body visibly rests on its named floor, plinth, shelf, wall, or other support while transformation occurs through that same object structure. "
        "Do not detach the monster body from the object or make the object hover unintentionally."
    ),
    "rearing-from-floor": (
        "REARING-FROM-FLOOR LOCK: the lower edge/base remains visibly in contact with the floor while the upper portion rises, bends, or wraps upward. "
        "The anchored base must explain the leverage; do not float the whole subject."
    ),
    "rooted": (
        "ROOTED LOCK: the stalk/base visibly grows from, penetrates, or spreads into the named floor/soil/wood/stone support. "
        "Upper structures may react or extend, but the rooted base remains stationary and unmistakably attached."
    ),
    "running": (
        "RUNNING LOCK: at least one canonical foot visibly contacts the ground while the other leg drives through a stride and the torso leans along a clear travel direction. "
        "Do not use a neutral standing pose or an unsupported midair freeze-frame."
    ),
    "sliding-ooze": (
        "SLIDING-OOZE LOCK: the continuous ooze body keeps a broad visible contact edge with the floor and deforms along the direction of travel; where the page names walls/bars, side contact must also be visible. "
        "No walking limbs or floating gaps."
    ),
    "stepping-down": (
        "STEPPING-DOWN LOCK: show active weight transfer between two elevations: one foot/contact remains on the higher support while another reaches or bears weight on the lower surface. "
        "The pose must not read as simply standing on either level."
    ),
    "stepping-from-perch": (
        "STEPPING-FROM-PERCH LOCK: at least one canonical contact point remains on the perch while another reaches or contacts the destination surface. "
        "The transition path must be visible; do not convert the movement into hovering or flight unless the page explicitly calls for it."
    ),
    "tunnel-emergence": (
        "TUNNEL-EMERGENCE LOCK: the body visibly contacts the tunnel floor/walls around the opening while the leading anatomy advances through the route. "
        "The tunnel boundaries must frame the subject and prove both emergence direction and scale."
    ),
    "walking-turn": (
        "WALKING-TURN LOCK: at least one weight-bearing foot stays visibly planted while hips/torso/shoulders rotate into the new direction and the other leg advances around the turn. "
        "Do not substitute a static frontal pose."
    ),
    "web-hanging": (
        "WEB-HANGING LOCK: canonical legs/body contact tensioned web strands or web anchors at multiple visible support points, and those strands visibly carry the weight. "
        "Do not invent ropes, hooks, extra limbs, or unsupported hovering."
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
