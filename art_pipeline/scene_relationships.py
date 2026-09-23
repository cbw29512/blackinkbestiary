from __future__ import annotations

import json
import logging
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = ROOT / "data" / "scene_relationship_rules.json"
LOGGER = logging.getLogger(__name__)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load scene relationship rules: %s", path)
        raise RuntimeError(f"Could not load scene relationship rules {path}: {exc}") from exc


def load_relationship_rules(path: Path = RULES_FILE) -> dict:
    payload = _read_json(path)
    if not isinstance(payload.get("rules"), dict):
        raise RuntimeError("scene relationship registry requires rules")
    return payload


def _page_text(page: dict) -> str:
    variant = page.get("environment_variant") or {}
    physicality = page.get("physicality") or {}
    raw = " ".join([
        str(page.get("moment") or ""),
        str(page.get("archetype") or ""),
        " ".join(str(item) for item in page.get("must_include") or []),
        str(variant.get("landmark") or ""),
        str(variant.get("framing") or ""),
        str(variant.get("interaction") or ""),
        str(physicality.get("mode") or ""),
        str(physicality.get("support") or ""),
        str(physicality.get("motion") or ""),
    ])
    return " ".join(raw.lower().split())


def _term_matches(text: str, term: str) -> bool:
    normalized = " ".join(str(term or "").lower().split())
    if not normalized:
        return False
    pattern = rf"(?<!\\w){re.escape(normalized)}(?!\\w)"
    return re.search(pattern, text) is not None


def active_relationship_rules(page: dict, root: Path = ROOT) -> list[dict]:
    payload = load_relationship_rules(root / "data" / "scene_relationship_rules.json")
    text = _page_text(page)
    matches = []
    for order, (rule_id, rule) in enumerate(payload["rules"].items()):
        terms = [str(item) for item in rule.get("trigger_terms") or []]
        if any(_term_matches(text, term) for term in terms):
            matches.append({
                "rule_id": rule_id,
                "_registry_order": order,
                **rule,
            })
    matches.sort(
        key=lambda item: (
            -int(item.get("priority") or 0),
            int(item.get("_registry_order") or 0),
        )
    )
    maximum = int((payload.get("prompt_budget") or {}).get("max_active_rules") or 4)
    return [
        {key: value for key, value in item.items() if key != "_registry_order"}
        for item in matches[:maximum]
    ]


def relationship_prompt_lines(page: dict, root: Path = ROOT) -> list[str]:
    lines = []
    for rule in active_relationship_rules(page, root):
        directives = [str(item).strip() for item in rule.get("directives") or [] if str(item).strip()]
        if directives:
            label = rule["rule_id"].replace("_", " ").upper()
            lines.append(f"SCENE RELATIONSHIP — {label}: " + " ".join(directives))
    return lines


def relationship_review_checks(page: dict, root: Path = ROOT) -> list[str]:
    checks = []
    for rule in active_relationship_rules(page, root):
        for directive in rule.get("directives") or []:
            checks.append(f"Relationship check: {directive}")
    return checks
