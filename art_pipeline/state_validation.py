from __future__ import annotations


ACTIVE_STATES = {
    "queued",
    "generating",
    "qa_review",
    "supervisor_review",
    "awaiting_human",
    "modify_requested",
    "regenerate_requested",
    "generation_failed",
}


def validate_state(tome: dict, state: dict) -> list[str]:
    errors: list[str] = []
    ids = [page["page_id"] for page in tome.get("pages", [])]
    state_pages = state.get("pages") or {}
    current = state.get("current_page_id")

    if current not in ids:
        errors.append("current_page_id is not in the manifest")
    if set(state_pages) != set(ids):
        errors.append("production state page IDs do not match manifest")
        return errors

    active = [
        page_id
        for page_id, entry in state_pages.items()
        if entry.get("status") in ACTIVE_STATES
    ]
    if len(active) > 1:
        errors.append(f"more than one active page: {active}")
    if active and active[0] != current:
        errors.append("active page does not match current_page_id")

    for page_id, entry in state_pages.items():
        if not isinstance(entry.get("attempt", 0), int) or entry.get("attempt", 0) < 0:
            errors.append(f"{page_id}: attempt must be a non-negative integer")
        if not isinstance(entry.get("attempt_history", []), list):
            errors.append(f"{page_id}: attempt_history must be a list")

    if state.get("complete") and current != ids[-1]:
        errors.append("complete state must point at the final page")
    return errors


def assert_valid_state(tome: dict, state: dict) -> None:
    errors = validate_state(tome, state)
    if errors:
        raise ValueError("Production state invalid: " + " | ".join(errors))
