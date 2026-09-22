from __future__ import annotations

from prompt_builder import STYLE_RULES, _canonical_sections, _items, load_monster_spec


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
        f"STORY MOMENT MUST READ AS: {page['moment']}.",
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

    sections.append(
        "Make the smallest set of edits needed to satisfy the requirements. "
        "Keep every successful part of the provided image unchanged. "
        "Return one clean black-on-white printable coloring page."
    )
    return "\n\n".join(part for part in sections if part)
