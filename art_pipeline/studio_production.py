from __future__ import annotations

from . import studio_store as store
from . import studio_worker as worker
from .quality_system import expand_defect_tags, recommended_action
from .rebuild_state import activate_rebuild_source

VALID_DECISIONS = {"approve", "modify", "regenerate"}


def public_state() -> dict:
    tome, state = store.load_tome(), store.load_state()
    store.validate_state(tome, state)
    current = store.page_by_id(tome, state["current_page_id"])
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
        "current_monster_spec": store.public_monster_spec(current),
        "current_state": state["pages"][state["current_page_id"]],
        "current_page_id": state["current_page_id"],
        "generation_worker": worker.generation_worker_status(),
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

    entry["approved_image_path"] = store.archive_approved_candidate(
        tome, page_id, candidate
    )
    entry["status"] = "locked"
    entry["approved_candidate"] = candidate
    entry["approved_at"] = store.utc_now()
    entry["last_decision"] = "approve"

    order = [page["page_id"] for page in tome["pages"]]
    index = order.index(page_id)
    if index + 1 >= len(order):
        state["complete"] = True
        return

    next_id = order[index + 1]
    state["current_page_id"] = next_id
    if not activate_rebuild_source(state, next_id, store.WEB_DIR):
        state["pages"][next_id]["status"] = "queued"


def apply_decision(decision: str, notes: str = "", quick_tags=None) -> dict:
    if decision not in VALID_DECISIONS:
        raise ValueError("Invalid decision")

    tags = list(quick_tags or [])
    requested = decision
    route = recommended_action(store.ROOT, tags) if tags else decision
    if decision == "modify" and route == "regenerate":
        decision = "regenerate"

    tome, state = store.load_tome(), store.load_state()
    store.validate_state(tome, state)
    page_id = state["current_page_id"]
    page = store.page_by_id(tome, page_id) or {}
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
            "at": store.utc_now(),
        }

    state["updated_at"] = store.utc_now()
    store.append_review({
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
        "remediation_directives": expand_defect_tags(store.ROOT, tags),
        "timestamp": store.utc_now(),
    })
    store.write_json(store.STATE_FILE, state)
    return public_state()
