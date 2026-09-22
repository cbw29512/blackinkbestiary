from __future__ import annotations

from pathlib import Path

try:
    from .monster_brief import build_monster_brief
except ImportError:
    from monster_brief import build_monster_brief


def _items(label: str, values) -> str:
    clean = [str(item).strip() for item in (values or []) if str(item).strip()]
    return f"{label}: " + "; ".join(clean) + "." if clean else ""


def monster_prompt_sections(spec: dict | None, root: Path) -> list[str]:
    if not spec:
        return []
    brief = build_monster_brief(spec, root)
    visual = spec.get("visual_identity") or {}
    lines = [
        f"MONSTER BRIEF — AUTHORITATIVE: {brief['brief']}",
        _items("MONSTER IDENTITY ANCHORS", brief.get("anchors")),
        _items("MONSTER DRIFT TO AVOID", brief.get("avoid")),
        _items("MONSTER DRIFT CORRECTIONS", brief.get("corrections")),
        _items("VARIANT TRAITS", spec.get("variant_traits")),
        _items("CANONICAL GEAR", visual.get("signature_gear")),
        _items("CANONICAL ATTITUDE", visual.get("attitude")),
    ]
    mode = str(brief.get("subject_mode") or "")
    if mode and mode != "unspecified":
        lines.append(f"MONSTER SUBJECT MODE: {mode}.")
    count = str(brief.get("expected_count") or "")
    if count and count != "unspecified":
        lines.append(f"MONSTER EXPECTED COUNT: {count}.")
    body_plan = str(brief.get("body_plan") or "")
    if body_plan and body_plan != "unspecified":
        lines.append(f"MONSTER BODY PLAN: {body_plan}.")
    support = str(brief.get("support_logic") or "")
    if support and support != "unspecified":
        lines.append(f"MONSTER SUPPORT LOGIC: {support}.")
    return [line for line in lines if line]


def monster_review_checks(spec: dict | None) -> list[str]:
    if not spec:
        return []
    checks = [
        f"Identity check: {item}"
        for item in spec.get("accuracy_checks") or []
        if str(item).strip()
    ]
    checks.extend(
        f"Reject identity drift: {item.get('symptom')}"
        for item in spec.get("known_failure_modes") or []
        if item.get("symptom")
    )
    return checks
