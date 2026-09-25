from __future__ import annotations

from pathlib import Path

try:
    from .monster_catalog import load_monster_for_page
    from .page_contract import resolve_page_spec
except ImportError:
    from monster_catalog import load_monster_for_page
    from page_contract import resolve_page_spec

try:
    from .environment_prompt import environment_checklist, environment_compact_sections, environment_priority_sections, environment_prompt_sections, required_object_rules
    from .physicality_prompt import MODE_CONTACT_RULES, physicality_checklist, physicality_sections
    from .quality_system import archetype_directive, expand_defect_tags
    from .story_prompt import critical_scene_lock, interaction_proof_rules, story_checklist, story_sections
except ImportError:
    from environment_prompt import environment_checklist, environment_compact_sections, environment_priority_sections, environment_prompt_sections, required_object_rules
    from physicality_prompt import MODE_CONTACT_RULES, physicality_checklist, physicality_sections
    from quality_system import archetype_directive, expand_defect_tags
    from story_prompt import critical_scene_lock, interaction_proof_rules, story_checklist, story_sections

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


def _brief_items(label: str, values, limit: int | None = None) -> str:
    cleaned = []
    seen = set()
    for value in values or []:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        cleaned.append(item)
        if limit is not None and len(cleaned) >= limit:
            break
    return f"{label}: " + "; ".join(cleaned) + "." if cleaned else ""


def _review_recovery_lock(review_notes: dict | None) -> str:
    stage = str((review_notes or {}).get("stage") or "").strip().lower()
    text = str((review_notes or {}).get("text") or "").strip()
    if not text:
        return ""
    if stage == "identity":
        return (
            "IDENTITY RECOVERY LOCK — NON-NEGOTIABLE: the previous image failed species/anatomy review. "
            "Rebuild from canonical written authority and correct these visible failures: " + text + ". "
            "Do not preserve the failed silhouette."
        )
    if stage == "environment":
        return (
            "ENVIRONMENT RECOVERY LOCK — NON-NEGOTIABLE: the previous image failed environment geometry/identity review. "
            "Keep correct creature anatomy, but rebuild setting geometry so the setting must read correctly even if the creature is mentally removed. "
            "Correct: " + text + "."
        )
    if stage in {"action", "scene"}:
        return (
            "ACTION RECOVERY LOCK — NON-NEGOTIABLE: the previous image failed the required visible action/contact review. "
            "Rebuild pose, prop placement, support/contact, and cause-and-effect. The required verb must be visible without a caption. "
            "Correct: " + text + "."
        )
    if stage == "quality":
        return (
            "QUALITY RECOVERY LOCK — NON-NEGOTIABLE: the previous image failed printable coloring-page quality review. "
            "Preserve correct identity, setting, and action while simplifying density. Broad white colorable regions are mandatory. "
            "Correct: " + text + "."
        )
    return f"LATEST REVIEW CORRECTION: {text}"


def build_prompt(page: dict, review_notes: dict | None = None, candidate_no: int | None = None) -> str:
    """Compile full page authority into a short, priority-ordered FLUX brief.

    Full-fidelity authority remains in monster/environment/page data and the
    downstream verification checklist. The model-facing prompt intentionally
    removes repeated prose so hard anatomy/action/environment requirements do
    not compete with dozens of lower-priority restatements.
    """
    page = resolve_page_spec(page, ROOT)
    spec = load_monster_spec(page) or {}
    visual = spec.get("visual_identity") or {}
    scene = spec.get("scene_identity") or {}
    variant = page.get("environment_variant") or {}
    physicality = page.get("physicality") or {}
    render_priority = visual.get("render_priority") or {}
    review_stage = str((review_notes or {}).get("stage") or "").strip().lower()
    review_text = str((review_notes or {}).get("text") or "").strip()
    identity_focus_mode = bool(
        review_stage == "identity"
        and (review_notes or {}).get("stagnation_escalation")
    )

    size = str(spec.get("size") or "").strip().lower() or "unspecified"
    failures = [
        f"{item.get('symptom', '')} CORRECTION: {item.get('correction', '')}"
        for item in spec.get("known_failure_modes") or []
        if item.get("symptom") and item.get("correction")
    ]

    identity_lines = [
        f"SUBJECT: {page['monster_name']}.",
        (
            f"CANONICAL SCALE LOCK — NON-NEGOTIABLE: size category {size}. "
            f"{page.get('subject_scale_rule', '')} Canonical creature scale is immutable; use framing rather than enlarging the body. "
            "The monster remains the first-read focal subject through framing; it stays the first-read focal subject at canonical scale and proportions."
        ),
        f"SHAPE-FIRST RENDER LOCK — NON-NEGOTIABLE: {visual.get('shape_lock', '')}",
        f"CANONICAL SILHOUETTE: {visual.get('silhouette', '')}",
        f"CANONICAL BODY: {visual.get('body_shape', '')}",
        f"CANONICAL LIMBS / EXTREMITIES: {visual.get('limb_structure', '')}",
        f"CANONICAL SIZE IMPRESSION: {scene.get('size_impression', '')}",
        f"CANONICAL NATURAL POSTURE: {scene.get('natural_posture', '')}",
        _brief_items("CANONICAL BEHAVIOR STYLE", scene.get("behavior_style"), 4),
        _brief_items("CREATURE-REQUIRED PHYSICAL RELATIONSHIPS", spec.get("physical_requirements"), 3),
        _brief_items("ANATOMY THAT MUST REMAIN", visual.get("must_keep"), 6),
        _brief_items("ANATOMY THAT MUST NEVER APPEAR", visual.get("must_avoid"), 8),
        _brief_items("PAGE-SPECIFIC MONSTER IDENTITY", page.get("identity_rules"), 7),
        _brief_items("KNOWN IDENTITY DRIFT TO PREVENT", failures),
    ]
    for key, label in (
        ("positive", "MODEL PRIORITY CAPSULE — READ BEFORE STYLE OR SCENERY"),
        ("negative", "MODEL PRIORITY NEGATIVE LOCK — NON-NEGOTIABLE"),
    ):
        value = str(render_priority.get(key) or "").strip()
        if value:
            identity_lines.append(f"{label}: {value}")

    identity_lines.append(
        "ANATOMICAL INTEGRITY LOCK — NON-NEGOTIABLE: Never invent or duplicate heads, eyes, horns, antennae, arms, hands, "
        "legs, feet, wings, tails, tentacles, mandibles, pincers, or other appendages. Limbs attach once at plausible joints and may not branch, "
        "merge, or sprout from scenery. Exact canonical counts are hard limits. Candidate variation may change pose only; it may not change anatomy."
    )
    identity_lines.append(
        "CREATURE/SCENERY OWNERSHIP FIREWALL: scenery and props may touch the creature only where the recipe requires interaction; "
        "they may never sprout from, merge into, replace, or duplicate limbs, tails, wings, horns, antennae, mandibles, or other anatomy."
    )

    if _is_swarm(page, spec):
        identity_lines.extend(_swarm_priority_sections(page, spec))
        identity_lines.append(
            "SWARM COMPOSITION LOCK — NON-NEGOTIABLE: use the canonical controlled population as a hard composition limit; do not exceed it. "
            "The collective swarm is one readable directional shape with broad negative-space gaps; no single oversized member may dominate and no giant leader."
        )

    recovery_lock = _review_recovery_lock(review_notes)

    sections = [
        "Create ONE printable fantasy monster coloring-book page.",
        (
            "PRIORITY ORDER — OBEY IN THIS ORDER: 1) exact creature body plan/anatomy, 2) canonical size/proportions, "
            "3) the one visible story action/contact, 4) unmistakable environment geometry, 5) clean coloring-book style. "
            "If lower-priority detail conflicts with a higher-priority requirement, remove the lower-priority detail."
        ),
        recovery_lock,
        "IDENTITY — HIGHEST PRIORITY:\n" + "\n".join(f"- {x}" for x in identity_lines if x and not x.endswith(":")),
    ]

    sections.extend(environment_priority_sections(page, ROOT))

    if identity_focus_mode:
        sections.extend([
            (
                "IDENTITY-FIRST RECOVERY MODE — TEMPORARY INTERMEDIATE PASS: solve creature silhouette, exact limb topology, "
                "canonical body mass, head/body proportions, and size evidence before full narrative scenery. Keep only the largest habitat cue "
                "and one scale reference. Omit secondary props, repeated texture, micro-detail, and optional story clutter."
            ),
            f"HABITAT: {page['habitat']}.",
            (
                "BLACK-INK COLORABILITY LOCK: pure black contour lines on white paper; bold outer contour, lighter simple interior lines, "
                "large uninterrupted white regions, no grayscale wash, no painterly shading, almost no crosshatching, and no large black masses."
            ),
            (
                "PAGE-EDGE LOCK — NON-NEGOTIABLE: reserve the outer eight percent as blank white print margin. "
                "Never draw a decorative rectangular border; architecture must not connect into a page-sized frame."
            ),
            format_generation_self_check(True),
        ])
    else:
        action_rules = list(interaction_proof_rules(page))
        object_rules = list(required_object_rules(page))
        mode = str(physicality.get("mode") or "").strip().lower()
        mode_rule = str(MODE_CONTACT_RULES.get(mode) or "").strip()
        physicality_priority = [x for x in physicality_sections(page)[3:5] if str(x or "").strip()]

        action_lines = [
            f"MOMENT: {page.get('moment', '')}.",
            f"STORY BEAT: {page.get('moment', '')}.",
            f"STORY/ENVIRONMENT INTERACTION: {variant.get('interaction', '')}.",
            f"PHYSICAL SUPPORT / CONTACT: {physicality.get('support', '')}.",
            f"PHYSICAL MOTION / WEIGHT: {physicality.get('motion', '')}.",
            *physicality_priority,
            *action_rules,
            (
                "STATIC STORY TEST: the page must read as one clear verb/action at thumbnail size, not as a character portrait "
                "or a monster merely holding props."
            ),
        ]
        environment_lines = [
            f"HABITAT: {page['habitat']}.",
            *environment_compact_sections(page, ROOT),
            f"UNIQUE BACKGROUND LANDMARK: {variant.get('landmark', '')}.",
            f"UNIQUE BACKGROUND FRAMING: {variant.get('framing', '')}.",
            f"MONSTER / ENVIRONMENT INTERACTION: {variant.get('interaction', '')}.",
            (
                "ENVIRONMENT SIMPLICITY RULE: use only two to four large habitat-defining forms. The setting must read without the monster, "
                "but decorative clutter, repeated masonry texture, rubble wallpaper, and tiny props are lower priority and should be omitted."
            ),
        ]

        sections.extend([
            (
                "CRITICAL SCENE LOCK — NON-NEGOTIABLE: "
                f"exact visible action={page.get('moment', '')}; interaction={variant.get('interaction', '')}; "
                f"support/contact={physicality.get('support', '')}; motion/weight={physicality.get('motion', '')}. "
                "Do not substitute standing, holding, posing, or mere proximity."
            ),
            "ACTION — SECOND PRIORITY:\n" + "\n".join(f"- {x}" for x in action_lines if x),
            "ENVIRONMENT — THIRD PRIORITY:\n" + "\n".join(f"- {x}" for x in environment_lines if x),
            _brief_items("MUST INCLUDE", page.get("must_include"), 10),
            _brief_items("MUST AVOID", page.get("must_avoid"), 8),
        ])

        if candidate_no is not None:
            escape_offset = int((review_notes or {}).get("composition_escape_offset") or 0)
            variant_index = (candidate_no - 1 + escape_offset) % len(CANDIDATE_COMPOSITIONS)
            composition = CANDIDATE_COMPOSITIONS[variant_index]
            sections.append(
                f"CANDIDATE {candidate_no} COMPOSITION LOCK: {composition}. "
                "Make camera, subject placement, pose, landmark relationship, and story interaction materially distinct while preserving anatomy and canonical scale."
            )

        sections.extend([
            (
                "BLACK-INK COLORABILITY LOCK: uncolored professional fantasy coloring-book line art, pure black ink on white paper, "
                "bold outer contour, lighter simple interior lines, medium-low detail, large uninterrupted white regions, and predominantly white negative space. "
                "NEVER fill a creature, shadow, liquid, fur, shell, ooze, clothing, or scenery with solid black merely because it is dark; no solid-black void. "
                "No grayscale wash, painterly shading, dense crosshatching, text, logo, or watermark. No large black masses."
            ),
            (
                "PAGE-EDGE LOCK — NON-NEGOTIABLE: reserve the outer eight percent of the page on every side as completely blank white print margin; "
                "no creature anatomy, weapons, tails, wings, webs, masonry, rails, grates, props, borders, or stray linework may enter that zone. "
                "Never draw a decorative rectangular border, inset artwork frame, comic panel box, picture-frame line, or enclosing rectangle. "
                "Local architectural lines must not connect into a page-sized frame."
            ),
            (
                "REFERENCE RULE: any reference image is for creature anatomy, silhouette, and identity only. "
                "Do not copy its composition, rendering, colors, pose, or background."
            ),
            (
                "COMPOSITION: one first-read focal subject through framing, with the first-read focal subject at canonical scale and proportions; "
                "full or nearly full silhouette, two to four large supporting habitat forms, broad white space, believable grounding, no heroic re-scaling."
            ),
            (
                "PAGE RECIPE LOCK — NON-NEGOTIABLE: the identity, action, habitat, landmark, interaction, and required elements stated above are authoritative; "
                "universal libraries may enrich them but may not replace them."
            ),
            format_generation_self_check(False),
        ])

    if review_notes:
        failed_dimensions = review_notes.get("failed_dimensions") or []
        route = str(review_notes.get("routing_recommendation") or "").strip()
        tags = review_notes.get("quick_tags") or []
        if failed_dimensions:
            sections.append(_brief_items("FAILED REVIEW REQUIREMENTS TO CORRECT", failed_dimensions))
        if route == "regenerate":
            sections.append(
                "REGENERATION RULE: rebuild the failed composition from canonical authority; do not preserve a bad layout or failed creature silhouette."
            )
        if review_notes.get("stagnation_escalation"):
            sections.append(
                "STAGNATION ESCAPE RULE: materially change camera/pose/landmark geometry while preserving canonical identity and required habitat/action."
            )
        if review_text and review_stage not in {"identity", "environment", "action", "scene", "quality"}:
            sections.append(f"LATEST REVIEW CORRECTION: {review_text}")
        if tags:
            sections.append(_brief_items("LATEST HUMAN QUICK CHANGES", tags))
            sections.append(_brief_items("REMEDIATION DIRECTIVES", expand_defect_tags(ROOT, tags), 8))

    return "\n\n".join(part for part in sections if str(part or "").strip())



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
