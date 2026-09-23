from __future__ import annotations

import json
import logging
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = ROOT / "config" / "creature_equipment_rules.json"
LOGGER = logging.getLogger(__name__)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load creature equipment rules: %s", path)
        raise RuntimeError(f"Could not load creature equipment rules {path}: {exc}") from exc


def load_equipment_rules(path: Path = RULES_FILE) -> dict:
    payload = _read_json(path)
    if not payload.get("weapon_terms"):
        raise RuntimeError("creature equipment rules require weapon_terms")
    return payload


def _normalized(value) -> str:
    return " ".join(str(value or "").lower().split())


def _page_text(page: dict) -> str:
    variant = page.get("environment_variant") or {}
    physicality = page.get("physicality") or {}
    values = [
        page.get("moment"), page.get("archetype"),
        variant.get("landmark"), variant.get("framing"), variant.get("interaction"),
        physicality.get("mode"), physicality.get("support"), physicality.get("motion"),
    ]
    return " ".join(_normalized(value) for value in values)


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(_normalized(term))}(?!\w)", text) is not None


def weapon_gear(spec: dict | None, root: Path = ROOT) -> list[str]:
    if not spec:
        return []
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    terms = [_normalized(item) for item in payload.get("weapon_terms") or []]
    gear = (spec.get("visual_identity") or {}).get("signature_gear") or []
    return [
        str(item).strip() for item in gear
        if str(item).strip() and any(_contains_term(_normalized(item), term) for term in terms)
    ]


def _weapon_nouns(weapon: str, payload: dict) -> list[str]:
    text = _normalized(weapon)
    return [
        _normalized(term) for term in payload.get("weapon_terms") or []
        if _contains_term(text, term)
    ]


def _has_grasping_limb(spec: dict | None) -> bool:
    if not spec:
        return False
    visual = spec.get("visual_identity") or {}
    text = _normalized(" ".join([
        str(spec.get("creature_type") or ""),
        str(visual.get("core_identity") or ""),
        str(visual.get("body_shape") or ""),
        str(visual.get("limb_structure") or ""),
    ]))
    if "weapon itself is the creature" in text or "no humanoid limbs" in text:
        return False
    return any(term in text for term in ("humanoid", "hand", "arm", "gauntlet", "grasping tentacle"))


def _explicitly_detached(weapon: str, page: dict, payload: dict) -> bool:
    states = [_normalized(item) for item in payload.get("detached_state_terms") or []]
    weapon_text = _normalized(weapon)
    page_text = _page_text(page)
    nouns = _weapon_nouns(weapon, payload)
    if any(state in weapon_text for state in states):
        return True
    for noun in nouns:
        for state in states:
            if re.search(rf"{re.escape(state)}.{{0,32}}(?<!\w){re.escape(noun)}(?!\w)", page_text):
                return True
            if re.search(rf"(?<!\w){re.escape(noun)}(?!\w).{{0,32}}{re.escape(state)}", page_text):
                return True
    return False


def _story_occupies_hands(page: dict, payload: dict) -> bool:
    text = _page_text(page)
    return any(_contains_term(text, term) for term in payload.get("story_hand_use_terms") or [])


def _page_names_weapon(weapon: str, page: dict, payload: dict) -> bool:
    text = _page_text(page)
    return any(_contains_term(text, noun) for noun in _weapon_nouns(weapon, payload))


def held_weapon_gear(spec: dict | None, page: dict, root: Path = ROOT) -> list[str]:
    if not _has_grasping_limb(spec):
        return []
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    busy = _story_occupies_hands(page, payload)
    return [
        weapon for weapon in weapon_gear(spec, root)
        if not _explicitly_detached(weapon, page, payload)
        and (not busy or _page_names_weapon(weapon, page, payload))
    ]


def secured_weapon_gear(spec: dict | None, page: dict, root: Path = ROOT) -> list[str]:
    if not _has_grasping_limb(spec):
        return []
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    busy = _story_occupies_hands(page, payload)
    return [
        weapon for weapon in weapon_gear(spec, root)
        if _explicitly_detached(weapon, page, payload)
        or (busy and not _page_names_weapon(weapon, page, payload))
    ]


def equipment_prompt_sections(spec: dict | None, page: dict, root: Path = ROOT) -> list[str]:
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    sections = []
    held = held_weapon_gear(spec, page, root)
    secured = secured_weapon_gear(spec, page, root)
    if held:
        directives = (payload.get("directives") or {}).get("held_weapon") or []
        sections.append("CREATURE EQUIPMENT RELATIONSHIP — HELD: "
                        + f"{'; '.join(held)}. " + " ".join(directives))
    if secured:
        directives = (payload.get("directives") or {}).get("secured_weapon") or []
        sections.append("CREATURE EQUIPMENT RELATIONSHIP — SECURED: "
                        + f"{'; '.join(secured)}. " + " ".join(directives))
    return sections


def equipment_review_checks(spec: dict | None, page: dict, root: Path = ROOT) -> list[str]:
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    checks = []
    for key, gear in (("held_weapon", held_weapon_gear(spec, page, root)),
                      ("secured_weapon", secured_weapon_gear(spec, page, root))):
        if not gear:
            continue
        prefix = f"Equipment contact ({'; '.join(gear)}): "
        checks.extend(prefix + str(item).strip()
                      for item in (payload.get("review_checks") or {}).get(key) or []
                      if str(item).strip())
    return checks
