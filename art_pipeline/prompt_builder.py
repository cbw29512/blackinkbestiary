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
    failures = [
        f"{item.get('symptom', '')} CORRECTION: {item.get('correction', '')}"
        for item in spec.get("known_failure_modes", [])
        if item.get("symptom") and item.get("correction")
    ]
    sections = [
        f"CANONICAL CREATURE TYPE: {spec.get('creature_type', '')}; size {spec.get('size', '')}.",
        f"CANONICAL CORE IDENTITY: {visual.get('core_identity', '')}".strip(),
        f"CANONICAL SILHOUETTE: {visual.get('silhouette', '')}".strip(),
        f"CANONICAL HEAD: {visual.get('head_features', '')}".strip(),
        f"CANONICAL BODY: {visual.get('body_shape', '')}".strip(),
        f"CANONICAL SURFACE: {visual.get('surface', '')}".strip(),
        _items("VARIANT TRAITS", spec.get("variant_traits")),
        _items("CANONICAL GEAR", visual.get("signature_gear")),
        _items("CANONICAL ATTITUDE", visual.get("attitude")),
        _items("IDENTITY FEATURES THAT MUST SURVIVE STYLIZATION", visual.get("must_keep")),
        _items("IDENTITY ERRORS TO AVOID", visual.get("must_avoid")),
        _items("KNOWN IDENTITY DRIFT TO PREVENT", failures),
    ]
    return [part for part in sections if part and not part.endswith(":")]


def build_prompt(page: dict, review_notes: dict | None = None) -> str:
    page = resolve_page_spec(page, ROOT)
    spec = load_monster_spec(page)
    sections = [
        "Create ONE printable fantasy monster coloring-book page.",
        f"SUBJECT: {page['monster_name']}.",
        *_canonical_sections(spec),
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
        if text:
            sections.append(f"LATEST HUMAN NOTE: {text}")
        if tags:
            sections.append(_items("LATEST HUMAN QUICK CHANGES", tags))
            sections.append(_items("REMEDIATION DIRECTIVES", expand_defect_tags(ROOT, tags)))

    sections.append(
        "Final test: the monster is the large centered or near-centered dominant focal subject and is unmistakable at thumbnail size. "
        "All three storytelling pillars must pass independently: "
        "the environment is unmistakably the named habitat and worth coloring, and the story moment is unmistakable. "
        "Monster and environment must feel physically connected through perspective, scale, and interaction. "
        "The finished page must still contain generous clean white areas for coloring."
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
