from __future__ import annotations


def connector_completeness_items(page: dict) -> list[str]:
    """Each scaffold connector needs the span plus two distinct endpoints."""
    items: list[str] = []
    cfg = page.get("scene_scaffold") or {}
    if not isinstance(cfg, dict):
        return items
    for primitive in cfg.get("primitives") or []:
        if str(primitive.get("type") or "").strip().lower() != "connector":
            continue
        role = str(primitive.get("role") or "connector").strip() or "connector"
        anchors = [str(a).strip() for a in (primitive.get("anchors") or []) if str(a).strip()]
        while len(anchors) < 2:
            anchors.append("fixed wall endpoint")
        items.append(
            f"visible {role} crossing the traversable path between two fixed anchors"
        )
        items.append(
            f"{role} first endpoint fixed to {anchors[0]}, not on the creature, tail, clothing, or gear"
        )
        items.append(
            f"{role} second endpoint fixed to {anchors[1]}, not on the creature, tail, clothing, or gear"
        )
    return items


def connector_must_avoid_items(page: dict) -> list[str]:
    items: list[str] = []
    cfg = page.get("scene_scaffold") or {}
    if not isinstance(cfg, dict):
        return items
    for primitive in cfg.get("primitives") or []:
        if str(primitive.get("type") or "").strip().lower() != "connector":
            continue
        role = str(primitive.get("role") or "connector").strip() or "connector"
        items.append(f"{role} attached to creature, tail, clothing, or gear")
        items.append(f"{role} with only one visible endpoint")
        items.append(f"{role} ending inside a hazard with no far-side anchor")
    return items
