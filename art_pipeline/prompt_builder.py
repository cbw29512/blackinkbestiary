from __future__ import annotations

import json
from pathlib import Path

try:
    from .environment_spec import checklist as environment_checklist
    from .environment_spec import prompt_sections as environment_prompt_sections
    from .quality_system import archetype_directive, expand_defect_tags
    from .style_rules import STYLE_RULES
except ImportError:
    from environment_spec import checklist as environment_checklist
    from environment_spec import prompt_sections as environment_prompt_sections
    from quality_system import archetype_directive, expand_defect_tags
    from style_rules import STYLE_RULES

ROOT = Path(__file__).resolve().parents[1]
MONSTER_DIR = ROOT / "data" / "monsters"


def _items(label: str, values) -> str:
    values = [str(v).strip() for v in (values or []) if str(v).strip()]
    if not values:
        return ""
    return f"{label}: " + "; ".join(values) + "."


def load_monster_spec(page: dict) -> dict | None:
    spec_id = str(page.get("monster_spec_id", "")).strip()
    if not spec_id:
        return None
    path = MONSTER_DIR / f"{spec_id}.json"
    if not path.exists():
        raise RuntimeError(f"Monster spec not found: {path}")
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("monster_id") != spec_id:
        raise RuntimeError(f"Monster spec ID mismatch in {path}")
    return spec


def _canonical_sections(spec: dict | None) -> list[str]:
    if not spec:
        return []
    visual = spec.get("visual_identity") or {}
    sections = [
        f"CANONICAL CREATURE TYPE: {spec.get('creature_type', '')}; size {spec.get('size', '')}.",
        f"CANONICAL CORE IDENTITY: {visual.get('core_identity', '')}".strip(),
        f"CANONICAL SILHOUETTE: {visual.get('silhouette', '')}".strip(),
        f"CANONICAL HEAD: {visual.get('head_features', '')}".strip(),
        f"CANONICAL BODY: {visual.get('body_shape', '')}".strip(),
        f"CANONICAL SURFACE: {visual.get('surface', '')}".strip(),
        _items("CANONICAL GEAR", visual.get("signature_gear")),
        _items("CANONICAL ATTITUDE", visual.get("attitude")),
        _items("IDENTITY FEATURES THAT MUST SURVIVE STYLIZATION", visual.get("must_keep")),
        _items("IDENTITY ERRORS TO AVOID", visual.get("must_avoid")),
    ]
    return [part for part in sections if part and not part.endswith(":")]


def build_prompt(page: dict, review_notes: dict | None = None) -> str:
    spec = load_monster_spec(page)
    sections = [
        "Create ONE printable fantasy monster coloring-book page.",
        f"SUBJECT: {page['monster_name']}.",
        *_canonical_sections(spec),
        f"HABITAT LABEL: {page['habitat']}.",
        *environment_prompt_sections(page),
        f"STORY MOMENT: {page['moment']}.",
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
        "Final three-gate test: (1) the monster is unmistakable and anatomically coherent; "
        "(2) the environment is unmistakable, specific, and worth coloring; "
        "(3) the story moment is immediately readable because the monster and environment visibly interact. "
        "All three must survive the coloring-book simplification."
    )
    return "\n\n".join(part for part in sections if part)



def build_supervisor_checklist(page: dict) -> list[str]:
    spec = load_monster_spec(page)
    checks = [
        f"Clearly recognizable as {page['monster_name']}",
        f"Habitat label reads as: {page['habitat']}",
        *environment_checklist(page),
        f"Scene moment reads as: {page['moment']}",
        "Monster remains clearly readable without reducing the environment to filler",
        "Large open white coloring regions",
        "Outer contours stronger than interior detail",
        "No grayscale wash or painterly shading",
        "No dense crosshatching or excessive tiny texture",
        "No text, border, logo, or watermark",
    ]
    if spec:
        checks.extend(f"Identity check: {item}" for item in spec.get("accuracy_checks", []))
    for item in page.get("must_include", []):
        checks.append(f"Required element present: {item}")
    return checks
