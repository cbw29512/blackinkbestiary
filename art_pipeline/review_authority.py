from __future__ import annotations

import json
from pathlib import Path


def required_exact_image_reviewer(root: Path) -> str:
    path = root / "config" / "quality_scorecard.json"
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(payload.get("exact_image_reviewer") or "").strip().lower()


def decision_is_authoritative(review: dict | None, root: Path) -> bool:
    required = required_exact_image_reviewer(root)
    if not required:
        return True
    reviewer = str((review or {}).get("reviewer") or "").strip().lower()
    return reviewer == required
