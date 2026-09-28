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
            anchors.append("wall endpoint")
        items.append(f"{role} across the path at shin height")
        items.append(f"{role} end A on {anchors[0]}, not the creature")
        items.append(f"{role} end B on {anchors[1]}, not the creature")
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
        items.append(f"{role} on creature, mouth, or gear")
        items.append(f"{role} with one endpoint")
        items.append(f"{role} hanging from a torch, sconce, or door handle")
        items.append(f"{role} diving into a pit or ending inside a hazard")
    return items
