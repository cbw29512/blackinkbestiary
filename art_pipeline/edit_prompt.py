from __future__ import annotations

from pathlib import Path

try:
    from .page_contract import resolve_page_spec
    from .prompt_builder import _brief_items, load_monster_spec
    from .environment_prompt import (
        environment_compact_sections,
        environment_priority_sections,
        required_object_rules,
    )
    from .physicality_prompt import MODE_CONTACT_RULES
    from .quality_system import expand_defect_tags
    from .generation_lint import assert_edit_ready
except ImportError:
    from page_contract import resolve_page_spec
    from prompt_builder import _brief_items, load_monster_spec
    from environment_prompt import (
        environment_compact_sections,
        environment_priority_sections,
        required_object_rules,
    )
    from physicality_prompt import MODE_CONTACT_RULES
    from quality_system import expand_defect_tags
    from generation_lint import assert_edit_ready

ROOT = Path(__file__).resolve().parents[1]


def _identity_capsule(page: dict, spec: dict, stage: str) -> list[str]:
    visual = spec.get("visual_identity") or {}
    size = str(spec.get("size") or "").strip().lower() or "unspecified"
    lines = [
        f"SUBJECT MUST REMAIN: {page['monster_name']}.",
        (
            f"CANONICAL SCALE LOCK — NON-NEGOTIABLE: size category {size}. "
            f"{page.get('subject_scale_rule', '')} Use framing rather than changing body mass."
        ),
        f"SHAPE-FIRST RENDER LOCK — NON-NEGOTIABLE: {visual.get('shape_lock', '')}",
        f"CANONICAL SILHOUETTE: {visual.get('silhouette', '')}",
        f"CANONICAL LIMBS / EXTREMITIES: {visual.get('limb_structure', '')}",
        _brief_items("ANATOMY THAT MUST REMAIN", visual.get("must_keep"), 5 if stage == "identity" else 3),
        _brief_items("ANATOMY THAT MUST NEVER APPEAR", visual.get("must_avoid"), 6 if stage == "identity" else 3),
    ]
    if stage == "identity":
        failures = [
            f"{item.get('symptom', '')} CORRECTION: {item.get('correction', '')}"
            for item in spec.get("known_failure_modes") or []
            if item.get("symptom") and item.get("correction")
        ]
        lines.extend([
            _brief_items("IDENTITY ACCURACY CHECKS", spec.get("accuracy_checks"), 6),
            _brief_items("KNOWN IDENTITY DRIFT TO CORRECT", failures, 4),
        ])
    lines.append(
        "ANATOMICAL INTEGRITY LOCK — NON-NEGOTIABLE: never invent, duplicate, branch, merge, or delete canonical heads, eyes, horns, antennae, arms, legs, wings, tails, tentacles, mandibles, or pincers."
    )
    return [line for line in lines if str(line or "").strip() and not str(line).endswith(":")]


def _scene_capsule(page: dict) -> list[str]:
    variant = page.get("environment_variant") or {}
    physicality = page.get("physicality") or {}
    mode = str(physicality.get("mode") or "").strip().lower()
    mode_rule = str(MODE_CONTACT_RULES.get(mode) or "").strip()
    return [
        f"STORY MOMENT MUST READ AS: {page.get('moment', '')}.",
        f"LANDMARK MUST REMAIN: {variant.get('landmark', '')}.",
        f"FRAMING MUST REMAIN RECOGNIZABLE AS: {variant.get('framing', '')}.",
        f"STORY/ENVIRONMENT INTERACTION MUST READ AS: {variant.get('interaction', '')}.",
        f"PHYSICAL SUPPORT / CONTACT MUST READ AS: {physicality.get('support', '')}.",
        f"PHYSICAL MOTION / WEIGHT MUST READ AS: {physicality.get('motion', '')}.",
        mode_rule,
        _brief_items("REQUIRED OBJECT PHYSICAL RULES", required_object_rules(page), 4),
        _brief_items("MUST INCLUDE", page.get("must_include"), 6),
    ]


def _environment_capsule(page: dict, stage: str) -> list[str]:
    priority = environment_priority_sections(page, ROOT)
    compact = environment_compact_sections(page, ROOT)
    if stage in {"environment", "scene"}:
        detail = compact
    elif stage == "action":
        keep_prefixes = (
            "PAGE ENVIRONMENT AUTHORITY",
            "ENVIRONMENT SPATIAL TYPE",
            "ENVIRONMENT MATERIAL LANGUAGE",
            "UNIQUE BACKGROUND LANDMARK",
            "UNIQUE BACKGROUND FRAMING",
            "MONSTER / ENVIRONMENT INTERACTION",
            "SPACE ENVELOPE",
            "SPACE MUST SHOW",
            "GLOBAL ENVIRONMENT STANDARD",
        )
        detail = [
            line for line in compact
            if any(str(line).startswith(prefix) for prefix in keep_prefixes)
        ]
    else:
        detail = compact[:4]
    return [
        f"HABITAT MUST READ AS: {page['habitat']}.",
        *priority,
        *detail,
        (
            "ENVIRONMENT PRESERVATION RULE: preserve successful setting identity, perspective, scale references, and story-critical interactions. "
            "Change only what the failed stage requires; never flatten the scene into a generic backdrop."
        ),
    ]


def build_edit_prompt(page: dict, review_notes: dict | None = None, candidate_no: int | None = None) -> str:
    """Build a compact, stage-first preservation prompt for image editing.

    The full authority remains in data and review checklists. The edit model sees
    the failed stage first, followed by only the identity/scene/environment facts
    needed to repair the current pixels without prompt dilution.
    """
    page = resolve_page_spec(page, ROOT)
    spec = load_monster_spec(page) or {}
    notes = review_notes or {}
    stage = str(notes.get("stage") or "").strip().lower()
    text = str(notes.get("text") or "").strip()
    tags = notes.get("quick_tags") or []
    failed_dimensions = notes.get("failed_dimensions") or []
    preserve_dimensions = notes.get("preserve_dimensions") or []

    if stage == "identity":
        repair_strategy = (
            "IDENTITY REBUILD MODE — NON-NEGOTIABLE: the subject anatomy/body plan is structurally wrong. "
            "Preserve only clearly successful background/environment elements. Rebuild the creature silhouette, scale, proportions, limb topology, and pose as needed from canonical written authority. "
            "Do NOT preserve incorrect anatomy, heroic mass, extra limbs, invented wings, wrong species proportions, or a pose that forces the wrong body plan."
        )
    elif stage == "environment":
        repair_strategy = (
            "ENVIRONMENT REBUILD MODE — NON-NEGOTIABLE: preserve correct creature identity, but rebuild architecture, spatial envelope, landmark, camera/framing, and contact geometry as needed until the named place is unmistakable. "
            "Do not preserve a generic setting merely because its line art is clean."
        )
    elif stage in {"scene", "action"}:
        repair_strategy = (
            "SCENE REBUILD MODE — NON-NEGOTIABLE: preserve correct creature anatomy and successful unrelated environment, but rebuild pose, prop placement, contact geometry, camera/framing, or environment structure as needed so the required action and place read literally. "
            "Do not preserve a neutral pose or generic setting merely because it is attractive."
        )
    elif stage == "quality":
        repair_strategy = (
            "QUALITY REPAIR MODE: preserve correct creature anatomy, scene action, perspective, and environment identity. "
            "Simplify clutter, swarm/web wallpaper density, borders, black fill, line density, and other print/colorability defects without redesigning successful structure."
        )
    else:
        repair_strategy = (
            "TARGETED REPAIR MODE: preserve successful parts, but written canonical authority outranks the input image. "
            "Rebuild any anatomy, scene, action, or environment element that conflicts with the requirements."
        )

    sections = [
        "EDIT THE PROVIDED CURRENT COLORING PAGE.",
        (
            "EDIT PRIORITY ORDER: fix the current failed stage first; preserve already-correct higher-priority identity whenever compatible; "
            "then preserve required story/environment relationships; keep clean coloring-page style throughout."
        ),
        repair_strategy,
        f"CURRENT REVIEW FAILURE — FIX THIS FIRST: {text}" if text else "",
        _brief_items("FAILED QUALITY DIMENSIONS — CORRECT", failed_dimensions, 8),
        _brief_items("PASSED QUALITY DIMENSIONS — PRESERVE", preserve_dimensions, 8),
        "IDENTITY AUTHORITY:
" + "\n".join(f"- {line}" for line in _identity_capsule(page, spec, stage)),
        "SCENE AUTHORITY:
" + "\n".join(f"- {line}" for line in _scene_capsule(page) if line),
        "ENVIRONMENT AUTHORITY:
" + "\n".join(f"- {line}" for line in _environment_capsule(page, stage) if line),
        (
            "BLACK-INK STYLE LOCK: pure black contour line art on white paper; bold outer contours, simple lighter interior lines, large uninterrupted white regions, medium-low detail, no grayscale wash, no painterly shading, no dense crosshatching, no text/logo/watermark, no decorative rectangular frame, and no large black masses."
        ),
        (
            "PAGE RECIPE LOCK — NON-NEGOTIABLE: subject identity, story moment, habitat, landmark, framing, interaction, support/contact, motion, and required elements are authoritative. "
            "The input image is evidence only; it cannot override written authority."
        ),
        (
            f"CANDIDATE {candidate_no} COMPOSITION IDENTITY MUST REMAIN RECOGNIZABLE, except where the failed stage explicitly requires moving the creature, camera, prop, or architecture."
            if candidate_no is not None else ""
        ),
    ]

    modify = page.get("modify") or {}
    sections.extend([
        _brief_items("PRESERVE", modify.get("preserve"), 5),
        _brief_items("CHANGE ONLY AS NEEDED", modify.get("change"), 5),
        _brief_items("DO NOT INTRODUCE", modify.get("avoid"), 5),
    ])

    if tags:
        sections.append(_brief_items("HUMAN QUICK CHANGES", tags, 6))
        sections.append(_brief_items("TARGETED REMEDIATION", expand_defect_tags(ROOT, tags), 8))

    if stage == "identity":
        final_instruction = (
            "Correct every listed identity/anatomy defect completely, even if that requires redrawing most or all of the creature. "
            "Preserve successful environment elements only where they do not force the wrong scale/body plan. "
            "Return one clean black-on-white printable coloring page."
        )
    elif stage == "environment":
        final_instruction = (
            "Correct every listed environment defect completely, even if that requires rebuilding architecture, changing camera/framing, or moving the creature enough to restore believable contact. "
            "Preserve correct creature anatomy and successful story elements where compatible. Keep every successful part that does not block the required environment correction."
        )
    elif stage in {"scene", "action"}:
        final_instruction = (
            "Correct every listed scene/action defect completely, even if that requires moving the creature, props, or camera and rebuilding affected environment geometry. "
            "Preserve correct anatomy and successful unrelated background elements. Keep every successful part that does not block the required visible action."
        )
    elif stage == "quality":
        final_instruction = (
            "Correct every listed quality defect while preserving correct anatomy, action, and environment structure. "
            "Keep every successful part; simplify only the clutter/density/print defect that failed."
        )
    else:
        final_instruction = (
            "Correct every listed defect without inventing unrelated changes. Keep every successful part of the provided image unchanged where compatible with written authority. "
            "Return one clean black-on-white printable coloring page."
        )
    sections.append(final_instruction)
    prompt = "\n\n".join(part for part in sections if str(part or "").strip())
    assert_edit_ready(page, prompt, ROOT)
    return prompt
