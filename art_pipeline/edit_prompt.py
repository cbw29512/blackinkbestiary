from __future__ import annotations

from pathlib import Path

from prompt_builder import _canonical_sections, _items, load_monster_spec
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
    sections = [
        "EDIT THE PROVIDED CURRENT COLORING PAGE. Do not redesign it from scratch.",
        (
            "Preserve the existing framing, camera angle, pose, perspective, successful anatomy, "
            "and successful background elements unless they conflict with the requirements below."
        ),
        f"SUBJECT MUST REMAIN: {page['monster_name']}.",
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

    sections.append(
        "Correct every listed defect across monster, environment, and story moment, but do not invent unrelated changes. "
        "Make the smallest set of edits needed to satisfy the requirements. "
        "Keep every successful part of the provided image unchanged. "
        "Return one clean black-on-white printable coloring page."
    )
    return "\n\n".join(part for part in sections if part)
