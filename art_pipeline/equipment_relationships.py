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


def _page_text(page: dict) -> str:
    variant = page.get("environment_variant") or {}
    physicality = page.get("physicality") or {}
    values = [
        page.get("moment"),
        page.get("archetype"),
        variant.get("landmark"),
        variant.get("framing"),
        variant.get("interaction"),
        physicality.get("mode"),
        physicality.get("support"),
        physicality.get("motion"),
    ]
    return " ".join(" ".join(str(value or "").lower().split()) for value in values)


def weapon_gear(spec: dict | None, root: Path = ROOT) -> list[str]:
    if not spec:
        return []
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    terms = [str(item).lower() for item in payload.get("weapon_terms") or []]
    gear = (spec.get("visual_identity") or {}).get("signature_gear") or []
    return [
        str(item).strip()
        for item in gear
        if str(item).strip()
        and any(
            re.search(rf"(?<!\w){re.escape(term)}(?!\w)", str(item).lower())
            for term in terms
        )
    ]


def _weapon_nouns(weapon: str, terms: list[str]) -> list[str]:
    text = str(weapon or "").lower()
    return [
        term
        for term in terms
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text)
    ]


def weapon_explicitly_detached(weapon: str, page: dict, root: Path = ROOT) -> bool:
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    page_text = _page_text(page)
    terms = [str(item).lower() for item in payload.get("weapon_terms") or []]
    states = [str(item).lower() for item in payload.get("detached_state_terms") or []]
    nouns = _weapon_nouns(weapon, terms)
    for noun in nouns:
        for state in states:
            left = rf"{re.escape(state)}.{{0,32}}(?<!\w){re.escape(noun)}(?!\w)"
            right = rf"(?<!\w){re.escape(noun)}(?!\w).{{0,32}}{re.escape(state)}"
            if re.search(left, page_text) or re.search(right, page_text):
                return True
    return False


def held_weapon_gear(spec: dict | None, page: dict, root: Path = ROOT) -> list[str]:
    return [
        weapon
        for weapon in weapon_gear(spec, root)
        if not weapon_explicitly_detached(weapon, page, root)
    ]


def equipment_prompt_sections(
    spec: dict | None,
    page: dict,
    root: Path = ROOT,
) -> list[str]:
    weapons = held_weapon_gear(spec, page, root)
    if not weapons:
        return []
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    directives = (payload.get("directives") or {}).get("held_weapon") or []
    return [
        "CREATURE EQUIPMENT RELATIONSHIP — HELD WEAPON: "
        + f"Depicted carried weapon(s): {'; '.join(weapons)}. "
        + " ".join(str(item).strip() for item in directives if str(item).strip())
    ]


def equipment_review_checks(
    spec: dict | None,
    page: dict,
    root: Path = ROOT,
) -> list[str]:
    weapons = held_weapon_gear(spec, page, root)
    if not weapons:
        return []
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    checks = (payload.get("review_checks") or {}).get("held_weapon") or []
    prefix = f"Weapon contact ({'; '.join(weapons)}): "
    return [
        prefix + str(item).strip()
        for item in checks
        if str(item).strip()
    ]
