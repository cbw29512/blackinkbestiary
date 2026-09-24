from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "test-gallery-state.json"
DECISIONS = ROOT / "review-previews" / "decisions.json"


def main() -> int:
    if not DECISIONS.exists() or not STATE.exists():
        return 0

    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    reviews = decisions.get("reviews", [])
    changed = False

    for review in reviews:
        page_id = str(review.get("page_id") or "")
        candidate = int(review.get("candidate") or 0)
        decision = str(review.get("decision") or "").lower()
        if not page_id or candidate < 1:
            continue

        for item in state.get("results", []):
            if str(item.get("page_id")) != page_id or int(item.get("candidate") or 0) != candidate:
                continue
            if decision == "reject":
                item["status"] = "assistant_rejected"
                item["assistant_review"] = {
                    "decision": "reject",
                    "notes": review.get("notes", ""),
                }
                changed = True
            elif decision == "approve":
                item["assistant_review"] = {
                    "decision": "approve",
                    "notes": review.get("notes", ""),
                }
                state.setdefault("selections", {})[page_id] = {
                    "candidate": candidate,
                    "source": "assistant_review",
                }
                changed = True

    if changed:
        STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print(f"Applied {len(reviews)} GitHub review decisions to local gallery state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
