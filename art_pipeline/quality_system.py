from __future__ import annotations

import json
from pathlib import Path

try:
    from .studio_config import active_book_paths
except ImportError:
    from studio_config import active_book_paths


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load quality configuration: {path}: {exc}") from exc


def defect_rules(root: Path) -> dict[str, dict]:
    payload = _load(active_book_paths(root)["quality_rules"])
    return payload.get("defects") or {}


def archetype_rules(root: Path) -> dict[str, str]:
    payload = _load(active_book_paths(root)["page_archetypes"])
    return payload.get("archetypes") or {}


def environment_standard(root: Path) -> dict:
    return _load(active_book_paths(root)["environment_standard"])


def environment_directives(root: Path) -> list[str]:
    payload = environment_standard(root)
    directives = [str(payload.get("principle") or "").strip()]
    directives.extend(
        str(item).strip() for item in (payload.get("generation_requirements") or [])
        if str(item).strip()
    )
    return [item for item in directives if item]


def environment_approval_checks(root: Path) -> list[str]:
    payload = environment_standard(root)
    return [
        str(item).strip() for item in (payload.get("approval_checks") or [])
        if str(item).strip()
    ]

def expand_defect_tags(root: Path, tags) -> list[str]:
    rules = defect_rules(root)
    directives = []
    for raw in tags or []:
        tag = str(raw).strip()
        if not tag:
            continue
        rule = rules.get(tag)
        directives.append(rule["directive"] if rule else tag)
    return directives


def recommended_action(root: Path, tags) -> str:
    rules = defect_rules(root)
    actions = {
        (rules.get(str(tag).strip()) or {}).get("action")
        for tag in tags or []
    }
    actions.discard(None)
    return "regenerate" if "regenerate" in actions else "modify"


def archetype_directive(root: Path, page: dict) -> str:
    archetype = str(page.get("archetype") or "default_scene").strip()
    rules = archetype_rules(root)
    if archetype not in rules:
        raise RuntimeError(f"Unknown page archetype: {archetype}")
    return rules[archetype]
