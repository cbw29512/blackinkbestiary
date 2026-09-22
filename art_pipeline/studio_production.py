from __future__ import annotations

from .quality_system import expand_defect_tags, recommended_action
from .rebuild_state import activate_rebuild_source
from .studio_store import (
    ROOT,
    STATE_FILE,
    WEB_DIR,
    append_review,
    archive_approved_candidate,
    load_state,
    load_tome,
    page_by_id,
    public_monster_spec,
    utc_now,
    validate_state,
    write_json,
)
from .studio_worker import generation_worker_status

VALID_DECISIONS = {"approve", "modify", "regenerate"}


def public_state() -> dict:
    tome = load_tome()
    state = load_state()
    validate_state(tome, state)
    current = page_by_id(tome, state["current_page_id"])
    approved = sum(
        1 for entry in state["pages"].values()
        if entry["status"] == "locked"
    )
    return {
        "tome": {
            "tome_id": tome["tome_id"],
            "title": tome["title"],
            "theme": tome["theme"],
            "total_pages": tome["total_pages"],
        },
        "progress": {"approved": approved, "total": tome["total_pages"]},
        "current_page": current,
        "current_monster_spec": public_monster_spec(current),
        "current_state": state["pages"][state["current_page_id"]],
        "current_page_id": state["current_page_id"],
        "generation_worker": generation_worker_status(),
        "ordered_pages": [
            {
                "page_id": page["page_id"],
                "monster_name": page["monster_name"],
                "status": state["pages"][page["page_id"]]["status"],
                "approved_image_path": state["pages"][page["page_id"]].get(
                    "approved_image_path"
                ),
            }
            for page in tome["pages"]
        ],
    }


def _approve(tome: dict, state: dict, page_id: str, candidate: dict) -> None:
    entry = state["pages"][page_id]
    if not candidate:
        raise ValueError("Cannot approve without a current candidate")
    if entry["status"] != "awaiting_human":
        raise ValueError("Page must be awaiting human review before approval")

    entry["approved_image_path"] = archive_approved_candidate(tome, page_id, candidate)
    entry["status"] = "locked"
    entry["approved_candidate"] = candidate
    entry["approved_at"] = utc_now()
    entry["last_decision"] = "approve"

    order = [page["page_id"] for page in tome["pages"]]
    index = order.index(page_id)
    if index + 1 >= len(order):
        state["complete"] = True
        return

    next_id = order[index + 1]
    state["current_page_id"] = next_id
    if not activate_rebuild_source(state, next_id, WEB_DIR):
        state["pages"][next_id]["status"] = "queued"


def apply_decision(decision: str, notes: str = "", quick_tags=None) -> dict:
    if decision not in VALID_DECISIONS:
        raise ValueError("Invalid decision")

    tags = list(quick_tags or [])
    requested = decision
    route = recommended_action(ROOT, tags) if tags else decision
    if decision == "modify" and route == "regenerate":
        decision = "regenerate"

    tome, state = load_tome(), load_state()
    validate_state(tome, state)
    page_id = state["current_page_id"]
    page = page_by_id(tome, page_id) or {}
    entry = state["pages"][page_id]
    candidate = entry.get("current_candidate")

    if decision == "approve":
        _approve(tome, state, page_id, candidate)
    else:
        entry["status"] = (
            "modify_requested" if decision == "modify" else "regenerate_requested"
        )
        entry["last_decision"] = decision
        entry["review_notes"] = {
            "text": notes.strip(),
            "quick_tags": tags,
            "at": utc_now(),
        }

    state["updated_at"] = utc_now()
    append_review({
        "book_id": tome.get("tome_id"),
        "book_title": tome.get("title"),
        "page_id": page_id,
        "monster_name": page.get("monster_name"),
        "environment_identity": (page.get("environment") or {}).get("identity"),
        "environment_anchors": (page.get("environment") or {}).get("anchors", []),
        "archetype": page.get("archetype"),
        "requested_decision": requested,
        "decision": decision,
        "routing_recommendation": route,
        "candidate": candidate,
        "approved_image_path": entry.get("approved_image_path"),
        "notes": notes.strip(),
        "quick_tags": tags,
        "remediation_directives": expand_defect_tags(ROOT, tags),
        "timestamp": utc_now(),
    })
    write_json(STATE_FILE, state)
    return public_state()
