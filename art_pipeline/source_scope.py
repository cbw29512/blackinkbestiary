from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPE_FILE = ROOT / "config" / "content_scope.json"


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load source-scope file {path}: {exc}") from exc


def load_content_scope(root: Path = ROOT) -> dict:
    return _read(root / "config" / "content_scope.json")


def load_monster_registry(root: Path = ROOT) -> dict:
    scope = load_content_scope(root)
    path = root / scope["monster_source_registry"]
    return _read(path)


def monster_allowed(monster_id: str, root: Path = ROOT) -> bool:
    registry = load_monster_registry(root)
    entry = (registry.get("monsters") or {}).get(str(monster_id or "").strip()) or {}
    return entry.get("status") == "allowed"


def source_scope_errors(monster_id: str, root: Path = ROOT) -> list[str]:
    monster_id = str(monster_id or "").strip()
    if not monster_id:
        return ["monster_id is required for source-scope validation"]
    if not monster_allowed(monster_id, root):
        return [f"{monster_id}: not allowed by 2024 SRD project roster"]
    return []
