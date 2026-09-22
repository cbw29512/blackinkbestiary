from __future__ import annotations

from pathlib import Path

from . import studio_store as store


def register_candidate(payload: dict) -> dict:
    from .studio_production import public_state

    tome, state = store.load_tome(), store.load_state()
    store.validate_state(tome, state)
    page_id = payload.get("page_id")
    if page_id != state["current_page_id"]:
        raise ValueError("Candidate can only be registered for the current page")

    image_path = str(payload.get("image_path", "")).strip()
    relative = Path(image_path)
    if not image_path:
        raise ValueError("image_path is required")
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("image_path must be a relative safe path")

    entry = state["pages"][page_id]
    attempt = int(entry.get("attempt", 0)) + 1
    candidate = {
        "candidate_id": payload.get("candidate_id") or f"{page_id}-A{attempt:03d}",
        "attempt": attempt,
        "image_path": image_path,
        "qa_status": payload.get("qa_status", "pass"),
        "supervisor_status": payload.get("supervisor_status", "ready_for_human"),
        "generation_mode": payload.get("generation_mode", "unknown"),
        "technical_retry": int(payload.get("technical_retry", 0)),
        "source": payload.get("source"),
        "created_at": store.utc_now(),
    }
    entry["attempt"] = attempt
    entry["current_candidate"] = candidate
    entry.setdefault("attempt_history", []).append(candidate)
    entry["status"] = "awaiting_human"
    state["updated_at"] = store.utc_now()
    store.write_json(store.STATE_FILE, state)
    return public_state()
