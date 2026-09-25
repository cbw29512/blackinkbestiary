from __future__ import annotations

from pathlib import Path

try:
    from .monster_catalog import load_monster_for_page
    from .page_contract import resolve_page_spec
except ImportError:
    from monster_catalog import load_monster_for_page
    from page_contract import resolve_page_spec

try:
    from .environment_prompt import environment_checklist, environment_priority_sections, environment_prompt_sections
    from .physicality_prompt import physicality_checklist, physicality_sections
    from .quality_system import archetype_directive, expand_defect_tags
    from .story_prompt import critical_scene_lock, story_checklist, story_sections
except ImportError:
    from environment_prompt import environment_checklist, environment_priority_sections, environment_prompt_sections
    from physicality_prompt import physicality_checklist, physicality_sections
    from quality_system import archetype_directive, expand_defect_tags
    from story_prompt import critical_scene_lock, story_checklist, story_sections

ROOT = Path(__file__).resolve().parents[1]
MONSTER_DIR = ROOT / "data" / "monsters"

try:
    from .style_rules import STYLE_RULES
except ImportError:
    from style_rules import STYLE_RULES



def _items(label: str, values) -> str:
    values = [str(v).strip() for v in (values or []) if str(v).strip()]
    if not values:
        return ""
    return f"{label}: " + "; ".join(values) + "."


def load_monster_spec(page: dict) -> dict | None:
    return load_monster_for_page(page)

def _is_swarm(page: dict, spec: dict | None) -> bool:
    return (
        str(page.get("archetype") or "") == "swarm_scene"
        or str((spec or {}).get("size") or "").lower() == "swarm"
        or str((spec or {}).get("creature_type") or "").lower().startswith("swarm of ")
    )


def _render_priority_sections(spec: dict | None) -> list[str]:
    """Short high-priority identity capsule for models prone to prompt dilution."""
    if not spec:
        return []
    priority = ((spec.get("visual_identity") or {}).get("render_priority") or {})
    if not isinstance(priority, dict):
        return []
    sections = []
    positive = str(priority.get("positive") or "").strip()
    negative = str(priority.get("negative") or "").strip()
    silhouette = str(priority.get("silhouette_test") or "").strip()
    if positive:
        sections.append(
            "MODEL PRIORITY CAPSULE — READ BEFORE STYLE OR SCENERY: " + positive
        )
    if negative:
        sections.append(
            "MODEL PRIORITY NEGATIVE LOCK — NON-NEGOTIABLE: " + negative
        )
    if silhouette:
        sections.append(
            "MODEL PRIORITY THUMBNAIL TEST — NON-NEGOTIABLE: " + silhouette
        )
    return sections


def _swarm_priority_sections(page: dict, spec: dict | None) -> list[str]:
    if not _is_swarm(page, spec):
        return []
    visual = (spec or {}).get("visual_identity") or {}
    silhouette = str(visual.get("silhouette") or "").strip()
    return [
        (
            "MODEL SWARM PRIORITY CAPSULE — READ BEFORE SCENERY: treat the swarm as one readable collective shape made from a controlled visible population, "
            "not as wallpaper. Arrange individuals in a few separated clusters along one clear direction of travel, with broad contiguous white gaps at least about one body-width wide between clusters."
        ),
        (
            "MODEL SWARM NEGATIVE LOCK — NON-NEGOTIABLE: no edge-to-edge carpet of repeated bodies, no uncountable crowd, no giant foreground leader, "
            "no single mascot animal, and no dense overlap that destroys individual silhouettes. Preserve the canonical population/scale rule: "
            + silhouette
        ),
    ]


def _body_plan_lock(page: dict, spec: dict | None) -> list[str]:
    """Build highest-priority species geometry and canonical-scale constraints."""
    if not spec:
        return []
    visual = spec.get("visual_identity") or {}
    size = str(spec.get("size") or "").strip().lower() or "unspecified"
    scale_rule = str(page.get("subject_scale_rule") or "").strip()
    sections = [
        (
            f"SHAPE-FIRST RENDER LOCK — NON-NEGOTIABLE: {visual.get('shape_lock', '')}"
            if str(visual.get("shape_lock") or "").strip()
            else ""
        ),
        (
            f"CANONICAL SCALE LOCK — NON-NEGOTIABLE: {page.get('monster_name', '')} is size category {size}. "
            f"{scale_rule} Canonical size outranks composition; framing may move closer, but body mass and proportions may not be enlarged or reduced to make the subject more dramatic."
        ),
        f"CANONICAL BODY PLAN LOCK — NON-NEGOTIABLE: {visual.get('silhouette', '')}",
        f"CANONICAL PROPORTION LOCK — NON-NEGOTIABLE: {visual.get('body_shape', '')}",
        f"CANONICAL LIMB TOPOLOGY LOCK — NON-NEGOTIABLE: {visual.get('limb_structure', '')}",
        _items("ANATOMY THAT MUST REMAIN", visual.get("must_keep")),
        _items("ANATOMY THAT MUST NEVER APPEAR", visual.get("must_avoid")),
        (
            "SPECIES LOCK — NON-NEGOTIABLE: do not reinterpret this subject as a generic fantasy hero, dragon-person, demon, orc, "
            "bodybuilder, furry brute, humanoid, or other familiar archetype unless that anatomy is explicitly part of the canonical creature description above. "
            "When the requested creature has an unusual non-humanoid body plan, preserve that body plan literally rather than forcing it onto a humanoid torso."
        ),
    ]
    if size in {"tiny", "small"}:
        sections.append(
            "SMALL-CREATURE SCALE LOCK: keep the torso, shoulders, limbs, head-to-body ratio, and overall mass visibly small. "
            "Use nearby architecture/props and a closer camera to make the subject readable; never solve composition by turning it into an adult-human-sized or heroic muscular creature."
        )
        creature_type = str(spec.get("creature_type") or "").lower()
        if "humanoid" in creature_type:
            sections.append(
                "SMALL-HUMANOID SCALE EVIDENCE — NON-NEGOTIABLE: show at least one human-scale architectural reference in the same depth plane. "
                "For an ordinary dungeon door/corridor, the creature's standing height should read roughly one-third to one-half of the full human-scale opening height, "
                "with visibly smaller hands, feet, shoulders, and gear. Do not enlarge the creature to fill the frame."
            )
    if _is_swarm(page, spec):
        sections.append(
            "INDIVIDUAL-SCALE LOCK: every swarm member keeps the same canonical small/tiny anatomy and broadly comparable scale. "
            "The GROUP may dominate the page; no individual may become a giant focal leader."
        )
    return [part for part in sections if part and not part.endswith(":")]


def _canonical_sections(spec: dict | None) -> list[str]:
    if not spec:
        return []
    visual = spec.get("visual_identity") or {}
    scene = spec.get("scene_identity") or {}
    failures = [
        f"{item.get('symptom', '')} CORRECTION: {item.get('correction', '')}"
        for item in spec.get("known_failure_modes", [])
        if item.get("symptom") and item.get("correction")
    ]
    sections = [
        f"CANONICAL CREATURE TYPE: {spec.get('creature_type', '')}; size {spec.get('size', '')}.",
        f"CREATURE DESCRIPTION: {spec.get('description', '')}".strip(),
        f"CANONICAL CORE IDENTITY: {visual.get('core_identity', '')}".strip(),
        f"CANONICAL SILHOUETTE: {visual.get('silhouette', '')}".strip(),
        f"CANONICAL HEAD: {visual.get('head_features', '')}".strip(),
        f"CANONICAL BODY: {visual.get('body_shape', '')}".strip(),
        f"CANONICAL LIMBS / EXTREMITIES: {visual.get('limb_structure', '')}".strip(),
        f"CANONICAL SURFACE: {visual.get('surface', '')}".strip(),
        f"CANONICAL SIZE IMPRESSION: {scene.get('size_impression', '')}".strip(),
        f"CANONICAL NATURAL POSTURE: {scene.get('natural_posture', '')}".strip(),
        _items("CANONICAL BEHAVIOR STYLE", scene.get("behavior_style")),
        _items("REUSABLE CREATURE BEHAVIOR TRAITS", spec.get("behavior_traits")),
        _items("CREATURE-REQUIRED PHYSICAL RELATIONSHIPS", spec.get("physical_requirements")),
        _items("VARIANT TRAITS", spec.get("variant_traits")),
        _items("CANONICAL GEAR", visual.get("signature_gear")),
        _items("CANONICAL ATTITUDE", visual.get("attitude")),
        _items("IDENTITY FEATURES THAT MUST SURVIVE STYLIZATION", visual.get("must_keep")),
        _items("IDENTITY ERRORS TO AVOID", visual.get("must_avoid")),
        _items("KNOWN IDENTITY DRIFT TO PREVENT", failures),
    ]
    return [part for part in sections if part and not part.endswith(":")]


CANDIDATE_COMPOSITIONS = [
    "eye-level three-quarter view; subject offset slightly left; environment landmark visible behind and to the right; clear foreground-to-background depth",
    "low three-quarter view; subject offset slightly right; story interaction prominent in the lower foreground; strong depth without cropping anatomy",
    "higher oblique view; subject near center; habitat geometry surrounds the subject asymmetrically; preserve broad open coloring regions",
    "side or diagonal narrative view; subject crosses the scene rather than posing frontally; landmark and interaction form a readable triangle with the subject",
]


def build_prompt(page: dict, review_notes: dict | None = None, candidate_no: int | None = None) -> str:
    page = resolve_page_spec(page, ROOT)
    spec = load_monster_spec(page)
    review_stage = str((review_notes or {}).get("stage") or "").strip().lower()
    review_text = str((review_notes or {}).get("text") or "").strip()
    identity_focus_mode = bool(
        review_stage == "identity"
        and (review_notes or {}).get("stagnation_escalation")
    )
    recovery_lock = ""
    if review_stage == "identity" and review_text:
        recovery_lock = (
            "IDENTITY RECOVERY LOCK — NON-NEGOTIABLE: the previous image failed species/anatomy review. "
            "Generate a fresh creature from canonical written authority and explicitly correct these visible failures: "
            + review_text
            + ". Do not imitate or preserve the failed creature silhouette from the prior attempt."
        )
    elif review_stage == "environment" and review_text:
        recovery_lock = (
            "ENVIRONMENT RECOVERY LOCK — NON-NEGOTIABLE: the previous image failed environment geometry/identity review. "
            "Keep canonical creature anatomy, but rebuild room/terrain geometry, camera, scale references, landmark placement, and supporting architecture as needed. "
            "The setting must read correctly even if the creature is mentally removed. Explicitly correct these visible failures: "
            + review_text
            + ". Do not preserve a generic or spatially wrong background."
        )
    elif review_stage in {"action", "scene"} and review_text:
        recovery_lock = (
            "ACTION RECOVERY LOCK — NON-NEGOTIABLE: the previous image failed the required visible action/contact review. "
            "Keep canonical creature identity and any correct setting geometry, but rebuild pose, prop placement, support/contact, and cause-and-effect as needed. "
            "The required verb must be visible without a caption. Explicitly correct these visible failures: "
            + review_text
            + ". Do not preserve a neutral pose or merely place the creature near the required prop."
        )
    elif review_stage == "quality" and review_text:
        recovery_lock = (
            "QUALITY RECOVERY LOCK — NON-NEGOTIABLE: the previous image failed printable coloring-page quality review. "
            "Preserve canonical identity, correct environment, and clear action while simplifying line density and repeated detail, removing decorative borders/inset frames, large black fills, grayscale, clutter, or wallpaper patterns as needed. "
            "Explicitly correct these visible failures: "
            + review_text
            + ". Broad white colorable regions and a clean silhouette are mandatory."
        )
    identity_focus_directive = ""
    if identity_focus_mode:
        identity_focus_directive = (
            "IDENTITY-FIRST RECOVERY MODE — TEMPORARY INTERMEDIATE PASS: solve the creature silhouette, exact limb topology, "
            "canonical body mass, head/body proportions, and size evidence before solving the full narrative scene. Keep the background "
            "deliberately simple: only the largest structural habitat cue and one human-scale reference needed to prove creature size. "
            "Omit secondary props, decorative scenery, repeated texture, micro-detail, and optional story clutter. Do not sacrifice identity "
            "to satisfy environment richness in this pass. Once identity passes, later environment/action repair stages may add the remaining scene detail."
        )

    environment_detail_sections = (
        [] if identity_focus_mode else environment_prompt_sections(page, ROOT)
    )
    story_detail_sections = (
        [] if identity_focus_mode else story_sections(page, ROOT)
    )
    physicality_detail_sections = (
        [] if identity_focus_mode else physicality_sections(page)
    )

    sections = [
        "Create ONE printable fantasy monster coloring-book page.",
        (
            "BLACK-INK COLORABILITY LOCK: This is an uncolored coloring-book page. Use black contour lines on white paper. "
            "NEVER fill a creature, shadow, liquid, fur, shell, ooze, clothing, or background region with solid black merely "
            "because its canonical color is dark or black. Communicate dark coloration with sparse contour/texture cues while "
            "leaving the interior predominantly white and colorable. No large black masses."
        ),
        (
            "PAGE-EDGE LOCK — NON-NEGOTIABLE: draw only the scene itself on the white page. "
            "Reserve the outer eight percent of the page on every side as completely blank white print margin: no creature anatomy, weapons, tails, wings, webs, masonry, rails, grates, props, borders, or stray linework may enter that zone. "
            "Never draw a decorative rectangular border, inset artwork frame, comic panel box, picture-frame line, or enclosing rectangle around the illustration. "
            "Architecture, webs, grates, rails, shelves, and masonry may form local straight lines, but they must not connect into a page-sized frame. "
            "Keep clean white print margins without outlining those margins."
        ),
        f"SUBJECT: {page['monster_name']}.",
        *_render_priority_sections(spec),
        *_body_plan_lock(page, spec),
        *_swarm_priority_sections(page, spec),
        *environment_priority_sections(page, ROOT),
        recovery_lock,
        identity_focus_directive,
        critical_scene_lock(page),
        (
            "ANATOMICAL INTEGRITY LOCK — NON-NEGOTIABLE: Treat every countable body structure in the canonical creature "
            "identity as exact, not approximate. Never invent or duplicate heads, faces, eyes, horns, antennae, arms, hands, "
            "fingers, legs, feet, wings, tails, tentacles, mandibles, pincers, or other appendages. A normal bilateral creature "
            "must keep a coherent left/right body plan; limbs must attach once at anatomically plausible joints and may not branch, "
            "merge, sprout from scenery, or appear as detached extras. If canonical anatomy says a structure is absent, do not add it. "
            "If canonical anatomy gives a number such as two arms, four legs, eight spider legs, one tail, or two wings, that number is "
            "an exact hard limit. Pose and camera angle may hide part of a limb behind the body, but may never create an extra limb to "
            "make the pose readable. Candidate variation may change pose only; it may not change anatomy."
        ),
        *_canonical_sections(spec),
        (
            "CREATURE-ONLY AUTHORITY: canonical monster data describes the creature only. Any place words inherited "
            "from legacy monster text are descriptive lore or scale context, never scenery instructions. Do not add walls, "
            "corridors, caves, treasure, pillars, furniture, ruins, water, vegetation, lighting, traps, or other background "
            "elements because the monster text mentions them. Build all scenery exclusively from the selected page environment. "
            "CREATURE/SCENERY OWNERSHIP FIREWALL: scenery must never become anatomy. Chains, ropes, roots, rails, beams, torches, "
            "rocks, web strands, tools, props, furniture, and architectural lines may touch the creature only where the page recipe "
            "explicitly requires a physical interaction. They may never sprout from, merge into, replace, or duplicate limbs, tails, "
            "wings, horns, antennae, mandibles, or other body structures."
        ),
        (
            "HABITAT EXPANSION RULE: broad creature habitat tags are compatibility inputs only. The universal environment engine must flesh the selected habitat into specific spatial geometry, surfaces, landmarks, lighting, depth, hazards, vegetation or water, architecture where appropriate, and supporting props without copying a canned monster scene.\n\n"
            "PAGE ENVIRONMENT AUTHORITY: the named HABITAT and resolved environment profile below are mandatory and "
            "override all general creature habitat preferences. Creature-family environment_fit data is planning-only "
            "and must never replace, broaden, or reinterpret this selected page environment."
        ),
        f"HABITAT: {page['habitat']}.",
        *environment_detail_sections,
        ("" if identity_focus_mode else f"MOMENT: {page['moment']}."),
        *story_detail_sections,
        *physicality_detail_sections,
        ("" if identity_focus_mode else f"SCENE ARCHETYPE: {page.get('archetype', 'default_scene')}."),
        ("" if identity_focus_mode else f"ARCHETYPE COMPOSITION RULE: {archetype_directive(ROOT, page)}"),
        _items("PAGE-SPECIFIC MONSTER IDENTITY", page.get("identity_rules")),
        _items("MUST INCLUDE", page.get("must_include")),
        _items("MUST AVOID", page.get("must_avoid")),
        f"COMPOSITION: {page.get('composition', '')}".strip(),
        "HOUSE STYLE: " + "; ".join(STYLE_RULES) + ".",
        (
            "REFERENCE RULE: any reference image is for creature anatomy, silhouette, and identity only. "
            "Do not copy its composition, rendering, colors, pose, or background. "
            "The final art must remain original Black-Ink coloring-book line art."
        ),
    ]

    sections.append(format_generation_self_check(identity_focus_mode))

    if candidate_no is not None:
        escape_offset = int((review_notes or {}).get("composition_escape_offset") or 0)
        variant_index = (candidate_no - 1 + escape_offset) % len(CANDIDATE_COMPOSITIONS)
        variant = CANDIDATE_COMPOSITIONS[variant_index]
        sections.append(
            f"CANDIDATE {candidate_no} COMPOSITION LOCK: {variant}. "
            "This candidate must be compositionally distinct from the other candidates for this page. "
            "Do not default to a centered frontal portrait when this lock specifies another view. "
            "Vary camera angle, subject placement, pose, landmark relationship, and story interaction while preserving canonical anatomy. "
            "Camera/framing may change apparent prominence but MUST NOT change canonical creature scale, body mass, or species proportions."
        )

    # Legacy page modify/preserve recipes apply only when editing an existing
    # source image. Fresh text-to-image generation has nothing to preserve and
    # must build directly from canonical monster/environment/page authority.

    if review_notes:
        tags = review_notes.get("quick_tags") or []
        text = review_text
        failed_dimensions = review_notes.get("failed_dimensions") or []
        route = str(review_notes.get("routing_recommendation") or "").strip()
        if failed_dimensions:
            sections.append(_items("FAILED REVIEW REQUIREMENTS TO CORRECT", failed_dimensions))
        if route == "regenerate":
            sections.append(
                "REGENERATION RULE: rebuild the failed composition from the canonical page recipe. "
                "Do not preserve a bad layout or failed creature silhouette merely because parts of the previous attempt were attractive."
            )
        if review_notes.get("stagnation_escalation"):
            sections.append(
                "STAGNATION ESCAPE RULE: the previous structural repair failed at the same review stage. "
                "Use the alternate composition lock above to change camera/pose/landmark geometry materially while preserving canonical identity and required habitat/action."
            )
        if text and review_stage not in {"identity", "environment", "action", "scene", "quality"}:
            sections.append(f"LATEST REVIEW CORRECTION: {text}")
        if tags:
            sections.append(_items("LATEST HUMAN QUICK CHANGES", tags))
            sections.append(_items("REMEDIATION DIRECTIVES", expand_defect_tags(ROOT, tags)))

    variant = page.get("environment_variant") or {}
    required = "; ".join(str(item) for item in page.get("must_include") or [])
    sections.append(
        "PAGE RECIPE LOCK — NON-NEGOTIABLE: "
        f"environment={page['habitat']}; "
        f"moment={page['moment']}; "
        f"landmark={variant.get('landmark', '')}; "
        f"interaction={variant.get('interaction', '')}; "
        f"required elements={required}. "
        "Universal family/component libraries may enrich these requirements but may not replace them."
    )
    if _is_swarm(page, spec):
        sections.append(
            "SWARM COMPOSITION LOCK — NON-NEGOTIABLE: the collective swarm is the dominant subject, not one oversized leader. "
            "Use a controlled population of similarly scaled individuals arranged in one readable directional flow with obvious origin, "
            "broad negative-space gaps, and no wallpaper density. If canonical swarm identity gives an approximate visible population range, "
            "treat that range as a hard composition limit: do not exceed it and do not replace it with an uncountable crowd. "
            "Vary the group silhouette, not the anatomy or scale of a single member."
        )
        subject_test = (
            "the collective swarm must dominate through one readable group shape and direction; no single oversized member may dominate; "
            "individuals remain countable enough to read while broad white gaps preserve colorability"
        )
    else:
        subject_test = "the monster must be the first-read focal subject through framing while preserving canonical size, body mass, and species proportions, and it must remain unmistakable at thumbnail size"

    sections.append(
        "Final test: COLORABILITY IS THE GOVERNING CONSTRAINT. The page must first be inviting and satisfying to color, "
        "with broad open regions, clean line hierarchy, and no fiddly density. Under that constraint, " + subject_test + "; the environment "
        "must be unmistakably the named habitat; and one simple story moment must read immediately. Monster and environment "
        "must feel physically connected through perspective, scale, and interaction. If story or environment detail competes "
        "with coloring usability, simplify the story/environment detail."
    )
    return "\n\n".join(part for part in sections if part)



def build_page_verification_checklist(page: dict) -> dict[str, list[str]]:
    """Canonical checklist shared by generation and every review gate."""
    page = resolve_page_spec(page, ROOT)
    spec = load_monster_spec(page)
    visual = (spec or {}).get("visual_identity") or {}
    subject_check = (
        "Swarm reads as one controlled collective subject with clear directional flow, broad negative-space gaps, and no oversized leader"
        if _is_swarm(page, spec)
        else "Monster is visually dominant through framing while preserving canonical size, body mass, and species proportions"
    )

    identity = [
        f"Clearly recognizable as {page['monster_name']}",
        f"Canonical scale reads as: {str((spec or {}).get('size') or '').lower()} — {page.get('subject_scale_rule', '')}",
        f"Canonical body plan reads as: {visual.get('silhouette', '')}; limbs: {visual.get('limb_structure', '')}",
        f"Shape-first body geometry reads as: {visual.get('shape_lock', '')}" if str(visual.get("shape_lock") or "").strip() else "",
        subject_check,
    ]
    if spec:
        identity.extend(f"Identity check: {item}" for item in spec.get("accuracy_checks", []))
        identity.extend(
            f"Reject identity drift: {item.get('symptom')}"
            for item in spec.get("known_failure_modes", [])
            if item.get("symptom")
        )

    environment_raw = environment_checklist(page, ROOT)
    environment = [f"Habitat reads as: {page['habitat']}"]
    environment.extend(
        item for item in environment_raw
        if not str(item).startswith("Environment check:")
        and not str(item).startswith("Colorability failure to reject:")
    )

    action = [f"Scene moment reads as: {page['moment']}"]
    action.extend(story_checklist(page, ROOT))
    action.extend(physicality_checklist(page))
    for item in page.get("must_include", []):
        action.append(f"Required element present: {item}")

    quality = [
        "Large open white coloring regions",
        "Outer contours stronger than interior detail",
        "No grayscale wash or painterly shading",
        "No dense crosshatching or excessive tiny texture",
        "No text, logo, or watermark; no decorative rectangular artwork frame or inset picture box; only normal blank page margins",
        "Outer print-safe margin remains blank white",
        "No accidental RGB/color contamination",
    ]
    quality.extend(
        item for item in environment_raw
        if str(item).startswith("Colorability failure to reject:")
    )

    def clean(values):
        result = []
        seen = set()
        for value in values:
            item = str(value or "").strip()
            if not item or item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    return {
        "identity": clean(identity),
        "environment": clean(environment),
        "action": clean(action),
        "quality": clean(quality),
    }


def build_supervisor_checklist(page: dict) -> list[str]:
    checklist = build_page_verification_checklist(page)
    return [
        item
        for stage in ("identity", "environment", "action", "quality")
        for item in checklist[stage]
    ]


def format_page_verification_checklist(
    page: dict,
    stages: tuple[str, ...] | None = None,
) -> str:
    checklist = build_page_verification_checklist(page)
    selected_stages = stages or ("identity", "environment", "action", "quality")
    lines = ["MANDATORY PAGE VERIFICATION CHECKLIST — EVERY ITEM MUST PASS:"]
    for stage in selected_stages:
        lines.append(stage.upper() + ":")
        lines.extend(f"- {item}" for item in checklist[stage])
    return "\n".join(lines)


def format_generation_self_check(identity_focus_mode: bool = False) -> str:
    if identity_focus_mode:
        return (
            "GENERATION SELF-CHECK — IDENTITY RECOVERY: before finalizing, verify exact species silhouette, canonical body mass, exact limb topology, "
            "correct size evidence, simple open line art, and clean white print margins. Do not add scene complexity until identity is correct."
        )
    return (
        "GENERATION SELF-CHECK — BEFORE FINALIZING: "
        "IDENTITY: exact species silhouette, body mass, limb topology, and canonical size; "
        "ENVIRONMENT: the selected habitat and unique landmark read through large structural forms; "
        "ACTION: the required verb/contact/cause-and-effect is visibly clear; "
        "QUALITY: broad white coloring regions, simple line density, no grayscale/color contamination, and blank print-safe margins. "
        "The downstream reviewer will enforce the complete resolved checklist."
    )
