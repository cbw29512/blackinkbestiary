from __future__ import annotations

import json
import logging
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = ROOT / "config" / "creature_equipment_rules.json"
LOGGER = logging.getLogger(__name__)


def load_equipment_rules(path: Path = RULES_FILE) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load creature equipment rules: %s", path)
        raise RuntimeError(f"Could not load creature equipment rules {path}: {exc}") from exc
    if not payload.get("weapon_terms"):
        raise RuntimeError("creature equipment rules require weapon_terms")
    return payload


def normalized(value) -> str:
    return " ".join(str(value or "").lower().split())


def contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(normalized(term))}(?!\w)", text) is not None


def page_text(page: dict) -> str:
    variant = page.get("environment_variant") or {}
    physicality = page.get("physicality") or {}
    values = [
        page.get("moment"), page.get("archetype"),
        variant.get("landmark"), variant.get("framing"), variant.get("interaction"),
        physicality.get("mode"), physicality.get("support"), physicality.get("motion"),
    ]
    return " ".join(normalized(value) for value in values)


def weapon_nouns(text: str, payload: dict) -> list[str]:
    clean = normalized(text)
    return [
        normalized(term) for term in payload.get("weapon_terms") or []
        if contains_term(clean, term)
    ]


def canonical_weapon_gear(spec: dict | None, payload: dict) -> list[str]:
    if not spec:
        return []
    gear = (spec.get("visual_identity") or {}).get("signature_gear") or []
    return [
        str(item).strip() for item in gear
        if str(item).strip() and weapon_nouns(item, payload)
    ]


def page_weapon_mentions(page: dict, payload: dict) -> list[str]:
    text = page_text(page)
    return [
        normalized(term) for term in payload.get("weapon_terms") or []
        if contains_term(text, term)
    ]


def has_grasping_limb(spec: dict | None) -> bool:
    if not spec:
        return False
    visual = spec.get("visual_identity") or {}
    text = normalized(" ".join([
        str(spec.get("creature_type") or ""),
        str(visual.get("core_identity") or ""),
        str(visual.get("body_shape") or ""),
        str(visual.get("limb_structure") or ""),
    ]))
    negative = (
        "weapon itself is the creature",
        "no humanoid limbs",
        "no added limbs",
        "no limbs",
        "no hands",
        "no arms",
        "no wielder",
    )
    if any(marker in text for marker in negative):
        return False
    positive = ("humanoid", "hand", "hands", "arm", "arms", "gauntlet", "gauntlets",
                "grasping tentacle", "grasping tentacles")
    return any(contains_term(text, term) for term in positive)


def story_occupies_hands(page: dict, payload: dict) -> bool:
    text = page_text(page)
    return any(contains_term(text, term) for term in payload.get("story_hand_use_terms") or [])


def _paired_state(text: str, noun: str, states: list[str]) -> bool:
    for state in states:
        state = normalized(state)
        left = rf"{re.escape(state)}.{{0,32}}(?<!\w){re.escape(noun)}(?!\w)"
        right = rf"(?<!\w){re.escape(noun)}(?!\w).{{0,32}}{re.escape(state)}"
        if re.search(left, text) or re.search(right, text):
            return True
    return False


def page_places_weapon_externally(item: str, page: dict, payload: dict) -> bool:
    text = page_text(page)
    return any(
        _paired_state(text, noun, payload.get("external_placement_terms") or [])
        for noun in weapon_nouns(item, payload)
    )


def item_is_body_secured(item: str, page: dict, payload: dict) -> bool:
    item_text = normalized(item)
    body_states = payload.get("body_secure_terms") or []
    if any(normalized(state) in item_text for state in body_states):
        return True
    text = page_text(page)
    return any(
        _paired_state(text, noun, body_states)
        for noun in weapon_nouns(item, payload)
    )


def weapon_items(spec: dict | None, page: dict, payload: dict) -> list[str]:
    canonical = canonical_weapon_gear(spec, payload)
    represented = {
        noun
        for item in canonical
        for noun in weapon_nouns(item, payload)
    }
    page_only = [
        noun for noun in page_weapon_mentions(page, payload)
        if noun not in represented
    ]
    return canonical + page_only
