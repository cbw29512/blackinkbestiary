from __future__ import annotations

import json
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = ROOT / "config" / "physicality_mode_rules.json"
LOGGER = logging.getLogger(__name__)


def load_mode_rules(path: Path = RULES_FILE) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load physicality mode rules: %s", path)
        raise RuntimeError(f"Could not load physicality mode rules {path}: {exc}") from exc
    if not isinstance(payload.get("groups"), dict):
        raise RuntimeError("physicality mode registry requires groups")
    return payload


def resolve_mode_group(mode: str, root: Path = ROOT) -> dict | None:
    mode = str(mode or "").strip()
    if not mode:
        return None
    payload = load_mode_rules(root / "config" / "physicality_mode_rules.json")
    matches = []
    for group_id, group in payload["groups"].items():
        if mode in [str(item) for item in group.get("modes") or []]:
            matches.append({"group_id": group_id, **group})
    if len(matches) > 1:
        raise RuntimeError(f"physicality mode {mode!r} maps to multiple groups")
    return matches[0] if matches else None


def mode_prompt_sections(page: dict, root: Path = ROOT) -> list[str]:
    mode = str((page.get("physicality") or {}).get("mode") or "").strip()
    group = resolve_mode_group(mode, root)
    if not group:
        return []
    label = group["group_id"].replace("_", " ").upper()
    directives = " ".join(
        str(item).strip()
        for item in group.get("directives") or []
        if str(item).strip()
    )
    return [f"UNIVERSAL PHYSICALITY — {label}: {directives}"]


def mode_review_checks(page: dict, root: Path = ROOT) -> list[str]:
    mode = str((page.get("physicality") or {}).get("mode") or "").strip()
    group = resolve_mode_group(mode, root)
    if not group:
        return []
    return [
        f"Physicality family {group['group_id']}: {str(item).strip()}"
        for item in group.get("directives") or []
        if str(item).strip()
    ]


def uncovered_modes(pages: list[dict], root: Path = ROOT) -> list[str]:
    missing = {
        str((page.get("physicality") or {}).get("mode") or "").strip()
        for page in pages
        if str((page.get("physicality") or {}).get("mode") or "").strip()
        and resolve_mode_group((page.get("physicality") or {}).get("mode"), root) is None
    }
    return sorted(missing)
