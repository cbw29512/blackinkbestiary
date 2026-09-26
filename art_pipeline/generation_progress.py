from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "generation-progress.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_generation_progress(
    page_id: str | None,
    monster_name: str | None,
    candidate: int | None,
    phase: str,
    *,
    message: str = "",
    status: str | None = None,
) -> dict:
    payload = {
        "page_id": page_id,
        "monster_name": monster_name,
        "candidate": candidate,
        "phase": phase,
        "message": message,
        "status": status,
        "updated_at": _now(),
    }
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(PATH)
    return payload
