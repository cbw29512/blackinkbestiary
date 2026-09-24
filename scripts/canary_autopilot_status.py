from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "test-gallery-state.json"
CANARY_PAGE_IDS = (
    "I-01", "I-04", "I-08", "I-10", "I-14", "I-16", "I-19", "I-20", "I-22",
)

RETRYABLE = {
    "failed",
    "technical_qa_failed",
    "vision_reviewer_failed",
    "assistant_rejected",
}


def classify(item: dict | None) -> str:
    if not item:
        return "needs_generation"
    assistant = item.get("assistant_review") or {}
    decision = str(assistant.get("decision") or "").lower()
    if decision == "approve":
        return "approved"
    if decision == "reject":
        return "needs_generation"

    status = str(item.get("status") or "")
    if status in RETRYABLE:
        return "needs_generation"
    if status in {"ready_for_review", "max_refinements_reached"}:
        return "awaiting_review"
    return "needs_generation"


def main() -> int:
    if not STATE.exists():
        print("AUTOPILOT STATUS: no gallery state yet; generation required.")
        return 10

    state = json.loads(STATE.read_text(encoding="utf-8"))
    results = {
        (str(item.get("page_id")), int(item.get("candidate") or 0)): item
        for item in state.get("results", [])
    }

    counts = {"approved": 0, "awaiting_review": 0, "needs_generation": 0}
    rows = []
    for page_id in CANARY_PAGE_IDS:
        item = results.get((page_id, 1))
        state_name = classify(item)
        counts[state_name] += 1
        rows.append((page_id, state_name, str((item or {}).get("status") or "missing")))

    print(
        "AUTOPILOT STATUS: "
        f"approved={counts['approved']}/{len(CANARY_PAGE_IDS)} "
        f"awaiting_review={counts['awaiting_review']} "
        f"needs_generation={counts['needs_generation']}"
    )
    for page_id, state_name, raw_status in rows:
        print(f"  {page_id}: {state_name} ({raw_status})")

    if counts["approved"] == len(CANARY_PAGE_IDS):
        return 0
    if counts["needs_generation"]:
        return 10
    return 20


if __name__ == "__main__":
    raise SystemExit(main())
