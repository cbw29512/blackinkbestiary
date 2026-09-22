from __future__ import annotations

import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load Studio configuration: {path}: {exc}") from exc


def load_studio_config(root: Path) -> dict:
    config_path = root / "config" / "studio.json"
    config = _load_json(config_path)
    active = config.get("active_book") or {}
    required = {"manifest", "state", "reviews"}
    missing = sorted(required.difference(active))
    if missing:
        raise RuntimeError(f"Studio active_book is missing: {', '.join(missing)}")
    return config


def resolve_root_path(root: Path, relative: str, label: str) -> Path:
    path = Path(str(relative).strip())
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"{label} must stay inside the project root")
    resolved = (root / path).resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise RuntimeError(f"{label} escapes the project root")
    return resolved


def active_book_paths(root: Path) -> dict[str, Path]:
    config = load_studio_config(root)
    active = config["active_book"]
    return {
        "manifest": resolve_root_path(root, active["manifest"], "active book manifest"),
        "state": resolve_root_path(root, active["state"], "active book state"),
        "reviews": resolve_root_path(root, active["reviews"], "active book reviews"),
        "quality_rules": resolve_root_path(root, config["quality_rules"], "quality rules"),
        "page_archetypes": resolve_root_path(root, config["page_archetypes"], "page archetypes"),
        "environment_standard": resolve_root_path(
            root,
            config["environment_standard"],
            "environment standard",
        ),
        "coloring_page_standard": resolve_root_path(
            root,
            config["coloring_page_standard"],
            "coloring page standard",
        ),
        "universal_page_contract": resolve_root_path(
            root,
            config["universal_page_contract"],
            "universal page contract",
        ),
        "universal_monster_contract": resolve_root_path(
            root,
            config["universal_monster_contract"],
            "universal monster contract",
        ),
        "kdp_print_standard": resolve_root_path(
            root,
            config["kdp_print_standard"],
            "KDP print standard",
        ),
        "content_scope": resolve_root_path(
            root,
            config["content_scope"],
            "content scope",
        ),
    }
