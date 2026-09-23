from __future__ import annotations

from pathlib import Path

try:
    from .monster_catalog import load_monster_for_page
    from .page_contract import resolve_page_spec
    from .prompt_parts import canonical_monster_sections, items_line, recipe_lock_line
except ImportError:
    from monster_catalog import load_monster_for_page
    from page_contract import resolve_page_spec
    from prompt_parts import canonical_monster_sections, items_line, recipe_lock_line

try:
    from .equipment_relationships import equipment_prompt_sections, equipment_review_checks
    from .environment_prompt import environment_checklist, environment_prompt_sections
    from .physicality_prompt import physicality_checklist, physicality_sections
    from .quality_system import archetype_directive, expand_defect_tags
    from .story_prompt import story_checklist, story_sections
except ImportError:
    from equipment_relationships import equipment_prompt_sections, equipment_review_checks
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




def load_monster_spec(page: dict) -> dict | None:
    return load_monster_for_page(page)

def build_prompt(page: dict, review_notes: dict | None = None) -> str:
    page = resolve_page_spec(page, ROOT)
    spec = load_monster_spec(page)
    sections = [
        "Create ONE printable fantasy monster coloring-book page.",
        f"SUBJECT: {page['monster_name']}.",
        *canonical_monster_sections(spec),
        *equipment_prompt_sections(spec, page, ROOT),
        (
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
        items_line("PAGE-SPECIFIC MONSTER IDENTITY", page.get("identity_rules")),
        items_line("MUST INCLUDE", page.get("must_include")),
        items_line("MUST AVOID", page.get("must_avoid")),
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
            items_line("PRESERVE", modify.get("preserve")),
            items_line("CHANGE", modify.get("change")),
            items_line("DO NOT CHANGE / DO NOT INTRODUCE", modify.get("avoid")),
            "This is a targeted refinement. Preserve the successful scene and simplify only the requested areas.",
        ])

    if review_notes:
        tags = review_notes.get("quick_tags") or []
        text = (review_notes.get("text") or "").strip()
        failed_dimensions = review_notes.get("failed_dimensions") or []
        route = str(review_notes.get("routing_recommendation") or "").strip()
        if failed_dimensions:
            sections.append(items_line("FAILED QUALITY DIMENSIONS TO REBUILD", failed_dimensions))
        if route == "regenerate":
            sections.append(
                "REGENERATION RULE: rebuild the failed composition from the canonical page recipe. "
                "Do not preserve a bad layout merely because parts of the previous attempt were attractive."
            )
        if text:
            sections.append(f"LATEST HUMAN NOTE: {text}")
        if tags:
            sections.append(items_line("LATEST HUMAN QUICK CHANGES", tags))
            sections.append(items_line("REMEDIATION DIRECTIVES", expand_defect_tags(ROOT, tags)))

    sections.append(recipe_lock_line(page))
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
    checks.extend(equipment_review_checks(spec, page, ROOT))
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
