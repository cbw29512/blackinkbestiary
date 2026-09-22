from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def activate_rebuild_source(state: dict, page_id: str, web_dir: Path) -> bool:
    """Promote a preserved rebuild source into the current review candidate."""
    entry = state["pages"][page_id]
    image_path = str(entry.get("rebuild_source_path") or "").strip()
    if not image_path:
        return False

    relative = Path(image_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe rebuild source path for {page_id}")

    source = (web_dir / relative).resolve()
    web_root = web_dir.resolve()
    if source != web_root and web_root not in source.parents:
        raise ValueError(f"Rebuild source escapes the Studio web root for {page_id}")
    if not source.exists() or not source.is_file():
        raise ValueError(f"Rebuild source is missing for {page_id}: {image_path}")

    attempt = int(entry.get("attempt", 0)) + 1
    candidate = {
        "candidate_id": f"{page_id}-REBUILD-SOURCE",
        "attempt": attempt,
        "image_path": image_path,
        "qa_status": "imported_rebuild_source",
        "supervisor_status": "needs_human_review",
        "generation_mode": "rebuild_source",
        "created_at": _utc_now(),
    }
    entry["attempt"] = attempt
    entry["current_candidate"] = candidate
    entry.setdefault("attempt_history", []).append(candidate)
    entry["status"] = "awaiting_human"
    return True
