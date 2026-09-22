from __future__ import annotations

from datetime import datetime, timezone


def build_production_state(tome: dict) -> dict:
    pages = {}
    for index, page in enumerate(tome.get("pages", [])):
        pages[page["page_id"]] = {
            "status": "queued" if index == 0 else "planned",
            "attempt": 0,
            "current_candidate": None,
            "approved_candidate": None,
            "attempt_history": [],
            "review_notes": None,
        }
    first = tome["pages"][0]["page_id"] if tome.get("pages") else None
    return {
        "version": 1,
        "current_page_id": first,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "complete": False,
        "pages": pages,
    }
