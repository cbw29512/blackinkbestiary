from __future__ import annotations


def prompt_items(label: str, values) -> str:
    clean = [str(value).strip() for value in (values or []) if str(value).strip()]
    if not clean:
        return ""
    return f"{label}: " + "; ".join(clean) + "."


def canonical_monster_sections(spec: dict | None) -> list[str]:
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
        f"CANONICAL CORE IDENTITY: {visual.get('core_identity', '')}".strip(),
        f"CANONICAL SILHOUETTE: {visual.get('silhouette', '')}".strip(),
        f"CANONICAL HEAD: {visual.get('head_features', '')}".strip(),
        f"CANONICAL BODY: {visual.get('body_shape', '')}".strip(),
        f"CANONICAL LIMBS / EXTREMITIES: {visual.get('limb_structure', '')}".strip(),
        f"CANONICAL SURFACE: {visual.get('surface', '')}".strip(),
        f"CANONICAL SIZE IMPRESSION: {scene.get('size_impression', '')}".strip(),
        f"CANONICAL NATURAL POSTURE: {scene.get('natural_posture', '')}".strip(),
        prompt_items("CANONICAL BEHAVIOR STYLE", scene.get("behavior_style")),
        prompt_items("VARIANT TRAITS", spec.get("variant_traits")),
        prompt_items("CANONICAL GEAR", visual.get("signature_gear")),
        prompt_items("CANONICAL ATTITUDE", visual.get("attitude")),
        prompt_items("IDENTITY FEATURES THAT MUST SURVIVE STYLIZATION", visual.get("must_keep")),
        prompt_items("IDENTITY ERRORS TO AVOID", visual.get("must_avoid")),
        prompt_items("KNOWN IDENTITY DRIFT TO PREVENT", failures),
    ]
    return [part for part in sections if part and not part.endswith(":")]
