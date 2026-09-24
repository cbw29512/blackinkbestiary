from __future__ import annotations

import hashlib
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


def _current_image_path(item: dict, root: Path = ROOT) -> Path:
    image_path = item.get("image_path")
    if image_path:
        return root / "web" / str(image_path)
    return root / "web" / "test-gallery" / (
        f"{item.get('page_id')}-C{int(item.get('candidate') or 0):02d}.png"
    )


def _current_review_id(item: dict, root: Path = ROOT) -> str | None:
    path = _current_image_path(item, root)
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return (
        f"{item.get('page_id')}-C{int(item.get('candidate') or 0):02d}-"
        f"H{digest[:16]}"
    )


def classify(item: dict | None, root: Path = ROOT) -> str:
    if not item:
        return "needs_generation"
    assistant = item.get("assistant_review") or {}
    decision = str(assistant.get("decision") or "").lower()
    recorded_review_id = str(assistant.get("review_id") or "")
    current_review_id = _current_review_id(item, root)
    exact_review_is_current = bool(
        recorded_review_id
        and current_review_id
        and recorded_review_id == current_review_id
    )
    if decision == "approve" and exact_review_is_current:
        return "approved"
    if decision == "reject" and exact_review_is_current:
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
