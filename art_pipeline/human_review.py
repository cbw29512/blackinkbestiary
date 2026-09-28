from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from .review_authority import decision_is_authoritative
except ImportError:
    from review_authority import decision_is_authoritative

VALID_DECISIONS = {"approve", "reject"}
VALID_STAGES = {"identity", "environment", "action", "completeness", "quality"}
REVIEWABLE_STATUSES = {
    "awaiting_exact_image_review",
    "ready_for_review",
    "max_refinements_reached",
    "technical_qa_stalled",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_image_path(root: Path, item: dict) -> Path:
    image_path = str(item.get("image_path") or "").strip()
    if image_path:
        return root / "web" / image_path
    return root / "web" / "test-gallery" / (
        f"{item.get('page_id')}-C{int(item.get('candidate') or 0):02d}.png"
    )


def exact_review_id(root: Path, item: dict) -> str:
    path = current_image_path(root, item)
    if not path.exists() or not path.is_file():
        raise ValueError(f"Current candidate image is missing: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return (
        f"{item.get('page_id')}-C{int(item.get('candidate') or 0):02d}-"
        f"H{digest[:16]}"
    )


def configured_canary_ids(root: Path) -> tuple[str, ...]:
    payload = json.loads(
        (root / "config" / "quality_scorecard.json").read_text(encoding="utf-8")
    )
    return tuple(str(x).strip() for x in payload.get("canary_page_ids") or [] if str(x).strip())


def current_canary_items(root: Path) -> list[dict]:
    state_path = root / "data" / "test-gallery-state.json"
    if not state_path.exists():
        return []
    state = json.loads(state_path.read_text(encoding="utf-8"))
    canaries = set(configured_canary_ids(root))
    rows = []
    for item in state.get("results", []):
        if str(item.get("page_id") or "") not in canaries:
            continue
        if int(item.get("candidate") or 0) != 1:
            continue
        if str(item.get("status") or "") not in REVIEWABLE_STATUSES:
            continue
        assistant = item.get("assistant_review") or {}
        try:
            review_id = exact_review_id(root, item)
        except ValueError:
            continue
        if (
            decision_is_authoritative(assistant, root)
            and str(assistant.get("decision") or "").strip().lower() in {"approve", "select"}
            and str(assistant.get("review_id") or "").strip() == review_id
        ):
            continue
        rows.append(item)
    order = {page_id: i for i, page_id in enumerate(configured_canary_ids(root))}
    return sorted(rows, key=lambda item: order.get(str(item.get("page_id")), 999))


def append_human_decision(
    root: Path,
    item: dict,
    decision: str,
    notes: str = "",
    stage: str = "",
) -> dict:
    decision = str(decision or "").strip().lower()
    stage = str(stage or "").strip().lower()
    notes = str(notes or "").strip()
    if decision not in VALID_DECISIONS:
        raise ValueError("Decision must be approve or reject.")
    if decision == "reject":
        if stage not in VALID_STAGES:
            raise ValueError("Rejected images require identity, environment, action, completeness, or quality stage.")
        if not notes:
            raise ValueError("Rejected images require a written reason.")

    review_id = exact_review_id(root, item)
    path = root / "review-previews" / "decisions.json"
    payload = {"reviews": []}
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    row = {
        "review_id": review_id,
        "page_id": str(item.get("page_id") or ""),
        "candidate": int(item.get("candidate") or 0),
        "decision": decision,
        "stage": stage if decision == "reject" else "quality",
        "notes": notes,
        "reviewer": "human",
        "decided_at": utc_now(),
    }
    payload.setdefault("reviews", []).append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return row
