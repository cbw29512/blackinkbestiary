from __future__ import annotations

from pathlib import Path

from prompt_builder import STYLE_RULES, _canonical_sections, _items, load_monster_spec
try:
    from .quality_system import archetype_directive, environment_directives, expand_defect_tags
except ImportError:
    from quality_system import archetype_directive, environment_directives, expand_defect_tags

ROOT = Path(__file__).resolve().parents[1]


def build_edit_prompt(page: dict, review_notes: dict | None = None) -> str:
    """Build a preservation-first prompt for editing the current candidate."""
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
        _items("GLOBAL ENVIRONMENT STANDARD", environment_directives(ROOT)),
        (
            "ENVIRONMENT PRESERVATION RULE: Preserve successful setting identity, perspective, scale references, "
            "and story-critical environmental interactions. Simplify clutter only; never flatten the scene into a generic backdrop."
        ),
        f"STORY MOMENT MUST READ AS: {page['moment']}.",
        f"SCENE ARCHETYPE MUST REMAIN: {page.get('archetype', 'default_scene')}.",
        f"ARCHETYPE COMPOSITION RULE: {archetype_directive(ROOT, page)}",
        _items("MUST INCLUDE", page.get("must_include")),
        _items("MUST AVOID", page.get("must_avoid")),
        f"COMPOSITION TARGET: {page.get('composition', '')}".strip(),
        "HOUSE STYLE MUST REMAIN: " + "; ".join(STYLE_RULES) + ".",
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
