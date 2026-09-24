from __future__ import annotations

from pathlib import Path

try:
    from .monster_catalog import load_monster_for_page
    from .page_contract import resolve_page_spec
except ImportError:
    from monster_catalog import load_monster_for_page
    from page_contract import resolve_page_spec

try:
    from .environment_prompt import environment_checklist, environment_prompt_sections
    from .physicality_prompt import physicality_checklist, physicality_sections
    from .quality_system import archetype_directive, expand_defect_tags
    from .story_prompt import story_checklist, story_sections
except ImportError:
    from environment_prompt import environment_checklist, environment_prompt_sections
    from physicality_prompt import physicality_checklist, physicality_sections
    from quality_system import archetype_directive, expand_defect_tags
    from story_prompt import story_checklist, story_sections

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
    sections = [
        "Create ONE printable fantasy monster coloring-book page.",
        (
            "BLACK-INK COLORABILITY LOCK: This is an uncolored coloring-book page. Use black contour lines on white paper. "
            "NEVER fill a creature, shadow, liquid, fur, shell, ooze, clothing, or background region with solid black merely "
            "because its canonical color is dark or black. Communicate dark coloration with sparse contour/texture cues while "
            "leaving the interior predominantly white and colorable. No large black masses."
        ),
        f"SUBJECT: {page['monster_name']}.",
        *_canonical_sections(spec),
        (
            "CREATURE-ONLY AUTHORITY: canonical monster data describes the creature only. Any place words inherited "
            "from legacy monster text are descriptive lore or scale context, never scenery instructions. Do not add walls, "
            "corridors, caves, treasure, pillars, furniture, ruins, water, vegetation, lighting, traps, or other background "
            "elements because the monster text mentions them. Build all scenery exclusively from the selected page environment."
        ),
        (
            "HABITAT EXPANSION RULE: broad creature habitat tags are compatibility inputs only. The universal environment engine must flesh the selected habitat into specific spatial geometry, surfaces, landmarks, lighting, depth, hazards, vegetation or water, architecture where appropriate, and supporting props without copying a canned monster scene.\n\n"
            "PAGE ENVIRONMENT AUTHORITY: the named HABITAT and resolved environment profile below are mandatory and "
            "override all general creature habitat preferences. Creature-family environment_fit data is planning-only "
            "and must never replace, broaden, or reinterpret this selected page environment."
        ),
        f"HABITAT: {page['habitat']}.",
        *environment_prompt_sections(page, ROOT),
        f"MOMENT: {page['moment']}.",
        *story_sections(page, ROOT),
        *physicality_sections(page),
        f"SCENE ARCHETYPE: {page.get('archetype', 'default_scene')}.",
        f"ARCHETYPE COMPOSITION RULE: {archetype_directive(ROOT, page)}",
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

    if candidate_no is not None:
        variant = CANDIDATE_COMPOSITIONS[(candidate_no - 1) % len(CANDIDATE_COMPOSITIONS)]
        sections.append(
            f"CANDIDATE {candidate_no} COMPOSITION LOCK: {variant}. "
            "This candidate must be compositionally distinct from the other candidates for this page. "
            "Do not default to a centered frontal portrait when this lock specifies another view. "
            "Vary camera angle, subject placement, pose, landmark relationship, and story interaction while preserving canonical anatomy."
        )

    modify = page.get("modify")
    if modify:
        sections.extend([
            _items("PRESERVE", modify.get("preserve")),
            _items("CHANGE", modify.get("change")),
            _items("DO NOT CHANGE / DO NOT INTRODUCE", modify.get("avoid")),
            "This is a targeted refinement. Preserve the successful scene and simplify only the requested areas.",
        ])

    if review_notes:
        tags = review_notes.get("quick_tags") or []
        text = (review_notes.get("text") or "").strip()
        failed_dimensions = review_notes.get("failed_dimensions") or []
        route = str(review_notes.get("routing_recommendation") or "").strip()
        if failed_dimensions:
            sections.append(_items("FAILED QUALITY DIMENSIONS TO REBUILD", failed_dimensions))
        if route == "regenerate":
            sections.append(
                "REGENERATION RULE: rebuild the failed composition from the canonical page recipe. "
                "Do not preserve a bad layout merely because parts of the previous attempt were attractive."
            )
        if text:
            sections.append(f"LATEST HUMAN NOTE: {text}")
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
    sections.append(
        "Final test: COLORABILITY IS THE GOVERNING CONSTRAINT. The page must first be inviting and satisfying to color, "
        "with broad open regions, clean line hierarchy, and no fiddly density. Under that constraint, the monster must be "
        "the large centered or near-centered dominant focal subject and unmistakable at thumbnail size; the environment "
        "must be unmistakably the named habitat; and one simple story moment must read immediately. Monster and environment "
        "must feel physically connected through perspective, scale, and interaction. If story or environment detail competes "
        "with coloring usability, simplify the story/environment detail."
    )
    return "\n\n".join(part for part in sections if part)



def build_supervisor_checklist(page: dict) -> list[str]:
    page = resolve_page_spec(page, ROOT)
    spec = load_monster_spec(page)
    checks = [
        f"Clearly recognizable as {page['monster_name']}",
        f"Habitat reads as: {page['habitat']}",
        f"Scene moment reads as: {page['moment']}",
        "Monster is large, centered or near-centered, and visually dominant",
        "Large open white coloring regions",
        "Outer contours stronger than interior detail",
        "No grayscale wash or painterly shading",
        "No dense crosshatching or excessive tiny texture",
        "No text, border, logo, or watermark",
    ]
    checks.extend(environment_checklist(page, ROOT))
    checks.extend(story_checklist(page, ROOT))
    checks.extend(physicality_checklist(page))
    if spec:
        checks.extend(f"Identity check: {item}" for item in spec.get("accuracy_checks", []))
        checks.extend(
            f"Reject identity drift: {item.get('symptom')}"
            for item in spec.get("known_failure_modes", [])
            if item.get("symptom")
        )
    for item in page.get("must_include", []):
        checks.append(f"Required element present: {item}")
    return checks
