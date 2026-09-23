from __future__ import annotations

from pathlib import Path

try:
    from .equipment_policy import canonical_weapon_gear, contains_term, load_equipment_rules
except ImportError:
    from equipment_policy import canonical_weapon_gear, contains_term, load_equipment_rules

ROOT = Path(__file__).resolve().parents[1]


def _normalize(value) -> str:
    return " ".join(str(value or "").lower().split())


def _signature_gear(spec: dict | None) -> list[str]:
    if not spec:
        return []
    return [
        str(item).strip()
        for item in ((spec.get("visual_identity") or {}).get("signature_gear") or [])
        if str(item).strip()
    ]


def _matches(item: str, terms: list[str]) -> bool:
    text = _normalize(item)
    return any(contains_term(text, term) for term in terms)


def attachment_assignments(spec: dict | None, root: Path = ROOT) -> list[dict]:
    payload = load_equipment_rules(root / "config" / "creature_equipment_rules.json")
    groups = payload.get("attachment_groups") or {}
    assignments = []
    weapons = set(canonical_weapon_gear(spec, payload))
    for item in _signature_gear(spec):
        if item in weapons:
            continue
        for group_id, group in groups.items():
            terms = [str(term) for term in group.get("trigger_terms") or []]
            if _matches(item, terms):
                assignments.append({
                    "item": item,
                    "group_id": group_id,
                    "directives": list(group.get("directives") or []),
                    "review_checks": list(group.get("review_checks") or []),
                })
                break
    return assignments


def attachment_prompt_sections(spec: dict | None, root: Path = ROOT) -> list[str]:
    sections = []
    for item in attachment_assignments(spec, root):
        directives = " ".join(
            str(value).strip()
            for value in item.get("directives") or []
            if str(value).strip()
        )
        label = item["group_id"].replace("_", " ").upper()
        sections.append(
            f"CREATURE GEAR ATTACHMENT — {label}: {item['item']}. {directives}"
        )
    return sections


def attachment_review_checks(spec: dict | None, root: Path = ROOT) -> list[str]:
    checks = []
    for item in attachment_assignments(spec, root):
        prefix = f"Gear attachment ({item['item']}): "
        checks.extend(
            prefix + str(value).strip()
            for value in item.get("review_checks") or []
            if str(value).strip()
        )
    return checks
