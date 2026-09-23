from __future__ import annotations

from pathlib import Path

try:
    from .equipment_policy import (
        canonical_weapon_gear,
        has_grasping_limb,
        item_is_body_secured,
        load_equipment_rules,
        page_places_weapon_externally,
        page_text,
        story_occupies_hands,
        weapon_items,
        weapon_nouns,
    )
except ImportError:
    from equipment_policy import (
        canonical_weapon_gear,
        has_grasping_limb,
        item_is_body_secured,
        load_equipment_rules,
        page_places_weapon_externally,
        page_text,
        story_occupies_hands,
        weapon_items,
        weapon_nouns,
    )

ROOT = Path(__file__).resolve().parents[1]


def _page_names_item(item: str, page: dict, payload: dict) -> bool:
    text = page_text(page)
    return any(noun in text.split() or f" {noun} " in f" {text} "
               for noun in weapon_nouns(item, payload))


def held_weapon_gear(spec: dict | None, page: dict, root: Path = ROOT) -> list[str]:
    if not has_grasping_limb(spec):
        return []
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    busy = story_occupies_hands(page, payload)
    held = []
    for item in weapon_items(spec, page, payload):
        if page_places_weapon_externally(item, page, payload):
            continue
        if item_is_body_secured(item, page, payload):
            continue
        is_canonical = item in canonical_weapon_gear(spec, payload)
        if is_canonical and busy and not _page_names_item(item, page, payload):
            continue
        held.append(item)
    return held


def secured_weapon_gear(spec: dict | None, page: dict, root: Path = ROOT) -> list[str]:
    if not has_grasping_limb(spec):
        return []
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    busy = story_occupies_hands(page, payload)
    secured = []
    for item in canonical_weapon_gear(spec, payload):
        if page_places_weapon_externally(item, page, payload):
            continue
        if item_is_body_secured(item, page, payload):
            secured.append(item)
            continue
        if busy and not _page_names_item(item, page, payload):
            secured.append(item)
    return secured


def equipment_prompt_sections(spec: dict | None, page: dict, root: Path = ROOT) -> list[str]:
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    sections = []
    held = held_weapon_gear(spec, page, root)
    secured = secured_weapon_gear(spec, page, root)
    if held:
        directives = (payload.get("directives") or {}).get("held_weapon") or []
        sections.append(
            "CREATURE EQUIPMENT RELATIONSHIP — HELD: "
            + f"{'; '.join(held)}. "
            + " ".join(str(item).strip() for item in directives if str(item).strip())
        )
    if secured:
        directives = (payload.get("directives") or {}).get("secured_weapon") or []
        sections.append(
            "CREATURE EQUIPMENT RELATIONSHIP — SECURED: "
            + f"{'; '.join(secured)}. "
            + " ".join(str(item).strip() for item in directives if str(item).strip())
        )
    return sections


def equipment_review_checks(spec: dict | None, page: dict, root: Path = ROOT) -> list[str]:
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    checks = []
    for key, gear in (
        ("held_weapon", held_weapon_gear(spec, page, root)),
        ("secured_weapon", secured_weapon_gear(spec, page, root)),
    ):
        if not gear:
            continue
        prefix = f"Equipment contact ({'; '.join(gear)}): "
        checks.extend(
            prefix + str(item).strip()
            for item in (payload.get("review_checks") or {}).get(key) or []
            if str(item).strip()
        )
    return checks
