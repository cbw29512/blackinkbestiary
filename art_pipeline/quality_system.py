from __future__ import annotations

import json
import logging
from pathlib import Path

try:
    from .studio_config import active_book_paths
except ImportError:
    from studio_config import active_book_paths

LOGGER = logging.getLogger(__name__)


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


def coloring_page_standard(root: Path) -> dict:
    return _load(active_book_paths(root)["coloring_page_standard"])


def coloring_page_directives(root: Path) -> list[str]:
    payload = coloring_page_standard(root)
    directives = []
    subject = (payload.get("composition_targets") or {}).get("primary_subject") or {}
    environment = (payload.get("composition_targets") or {}).get("environment") or {}
    if subject.get("rule"):
        directives.append(str(subject["rule"]))
    if environment.get("rule"):
        directives.append(str(environment["rule"]))
    directives.extend(str(item) for item in payload.get("shape_rules") or [])
    return [item.strip() for item in directives if str(item).strip()]


def coloring_page_failures(root: Path) -> list[str]:
    return [
        str(item).strip()
        for item in coloring_page_standard(root).get("automatic_failures") or []
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



def review_diagnosis(root: Path, tags) -> dict:
    """Classify review tags into failed and preserved production dimensions."""
    try:
        payload = _load(active_book_paths(root)["quality_rules"])
        dimensions = [
            str(item).strip()
            for item in payload.get("review_dimensions") or []
            if str(item).strip()
        ]
        rules = payload.get("defects") or {}
        failed: list[str] = []
        unknown: list[str] = []

        for raw in tags or []:
            tag = str(raw).strip()
            if not tag:
                continue
            rule = rules.get(tag)
            if not rule:
                unknown.append(tag)
                continue
            for dimension in rule.get("affects") or []:
                name = str(dimension).strip()
                if name and name not in failed:
                    failed.append(name)

        preserved = [item for item in dimensions if item not in failed]
        action = recommended_action(root, tags)

        if unknown:
            LOGGER.warning("Unknown review defect tags: %s", ", ".join(unknown))
        LOGGER.info(
            "Review diagnosis action=%s failed=%s preserved=%s",
            action,
            failed,
            preserved,
        )
        return {
            "action": action,
            "failed_dimensions": failed,
            "preserve_dimensions": preserved,
            "unknown_tags": unknown,
        }
    except Exception as exc:
        LOGGER.exception("Could not diagnose review tags")
        raise RuntimeError(f"Could not diagnose review tags: {exc}") from exc



def archetype_directive(root: Path, page: dict) -> str:
    archetype = str(page.get("archetype") or "default_scene").strip()
    rules = archetype_rules(root)
    if archetype not in rules:
        raise RuntimeError(f"Unknown page archetype: {archetype}")
    return rules[archetype]
