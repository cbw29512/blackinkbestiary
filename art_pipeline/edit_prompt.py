from __future__ import annotations

from pathlib import Path

from prompt_builder import _body_plan_lock, _canonical_sections, _items, load_monster_spec
try:
    from .page_contract import resolve_page_spec
except ImportError:
    from page_contract import resolve_page_spec
try:
    from .style_rules import STYLE_RULES
except ImportError:
    from style_rules import STYLE_RULES
try:
    from .environment_prompt import environment_prompt_sections
    from .physicality_prompt import physicality_sections
    from .quality_system import archetype_directive, expand_defect_tags
    from .story_prompt import story_sections
except ImportError:
    from environment_prompt import environment_prompt_sections
    from physicality_prompt import physicality_sections
    from quality_system import archetype_directive, expand_defect_tags
    from story_prompt import story_sections

ROOT = Path(__file__).resolve().parents[1]


def build_edit_prompt(page: dict, review_notes: dict | None = None, candidate_no: int | None = None) -> str:
    """Build a preservation-first prompt for editing the current candidate."""
    page = resolve_page_spec(page, ROOT)
    spec = load_monster_spec(page)
    stage = str((review_notes or {}).get("stage") or "").strip().lower()
    if stage == "identity":
        repair_strategy = (
            "IDENTITY REBUILD MODE — NON-NEGOTIABLE: the subject anatomy/body plan is structurally wrong. "
            "Preserve only clearly successful background/environment elements. Rebuild the creature silhouette, scale, proportions, limb topology, and pose as needed from the canonical written authority. "
            "Do NOT preserve incorrect anatomy, heroic mass, extra limbs, invented wings, wrong species proportions, or a pose that forces the wrong body plan."
        )
    elif stage in {"environment", "scene", "action"}:
        repair_strategy = (
            "SCENE REBUILD MODE — NON-NEGOTIABLE: preserve correct creature anatomy and coloring style, but rebuild pose, prop placement, contact geometry, camera/framing, or environment structure as needed so the required action and place read literally. "
            "Do not preserve a neutral pose or generic setting merely because it is attractive."
        )
    elif stage == "quality":
        repair_strategy = (
            "QUALITY REPAIR MODE: preserve correct creature anatomy, scene action, perspective, and environment identity. "
            "Simplify clutter, web/rat wallpaper density, borders, black fill, line density, and other print/colorability defects without redesigning the successful composition."
        )
    else:
        repair_strategy = (
            "TARGETED REPAIR MODE: preserve successful parts, but written canonical authority outranks the input image. "
            "Rebuild any anatomy, scene, or environment element that conflicts with the requirements."
        )

    sections = [
        "EDIT THE PROVIDED CURRENT COLORING PAGE.",
        repair_strategy,
        f"SUBJECT MUST REMAIN: {page['monster_name']}.",
        *_body_plan_lock(page, spec),
        *_canonical_sections(spec),
        f"HABITAT MUST READ AS: {page['habitat']}.",
        *environment_prompt_sections(page, ROOT),
        (
            "ENVIRONMENT PRESERVATION RULE: Preserve successful setting identity, perspective, scale references, "
            "and story-critical environmental interactions. Simplify clutter only; never flatten the scene into a generic backdrop."
        ),
        f"STORY MOMENT MUST READ AS: {page['moment']}.",
        *story_sections(page, ROOT),
        *physicality_sections(page),
        f"SCENE ARCHETYPE MUST REMAIN: {page.get('archetype', 'default_scene')}.",
        f"ARCHETYPE COMPOSITION RULE: {archetype_directive(ROOT, page)}",
        _items("MUST INCLUDE", page.get("must_include")),
        _items("MUST AVOID", page.get("must_avoid")),
        f"COMPOSITION TARGET: {page.get('composition', '')}".strip(),
        "HOUSE STYLE MUST REMAIN: " + "; ".join(STYLE_RULES) + ".",
        (
            f"CANDIDATE {candidate_no} COMPOSITION IDENTITY MUST REMAIN FIXED. "
            "Refinement may repair defects but must not drift into another candidate composition."
            if candidate_no is not None else ""
        ),
        (
            "ORIGINAL AUTHORITY OVERRIDES THE INPUT IMAGE. The provided image is evidence, not truth. "
            "If its anatomy, monster identity, environment, story beat, or coloring-page structure conflicts with "
            "the canonical monster/family/page requirements above, correct the image to match the written authority."
        ),
    ]

    modify = page.get("modify") or {}
    sections.extend([
        _items("PRESERVE", modify.get("preserve")),
        _items("CHANGE ONLY AS NEEDED", modify.get("change")),
        _items("DO NOT INTRODUCE", modify.get("avoid")),
    ])

    if review_notes:
        text = (review_notes.get("text") or "").strip()
        tags = review_notes.get("quick_tags") or []
        failed_dimensions = review_notes.get("failed_dimensions") or []
        preserve_dimensions = review_notes.get("preserve_dimensions") or []
        if preserve_dimensions:
            sections.append(_items("PASSED QUALITY DIMENSIONS — PRESERVE", preserve_dimensions))
        if failed_dimensions:
            sections.append(_items("FAILED QUALITY DIMENSIONS — CORRECT", failed_dimensions))
        if text:
            sections.append(f"HUMAN CORRECTION REQUEST: {text}")
        if tags:
            sections.append(_items("HUMAN QUICK CHANGES", tags))
            sections.append(_items("TARGETED REMEDIATION", expand_defect_tags(ROOT, tags)))

    if stage == "identity":
        final_instruction = (
            "Correct every listed identity/anatomy defect completely, even if that requires redrawing most or all of the creature. "
            "Preserve successful environment elements only where they do not force the wrong scale/body plan. "
            "Return one clean black-on-white printable coloring page."
        )
    elif stage == "scene":
        final_instruction = (
            "Correct every listed scene/physicality defect completely, even if that requires moving the creature, props, or camera and rebuilding affected environment geometry. "
            "Preserve correct anatomy and successful unrelated background elements. Return one clean black-on-white printable coloring page."
        )
    else:
        final_instruction = (
            "Correct every listed defect without inventing unrelated changes. Keep every successful part of the provided image unchanged where compatible with the written authority. "
            "Return one clean black-on-white printable coloring page."
        )
    sections.append(final_instruction)
    return "\n\n".join(part for part in sections if part)
