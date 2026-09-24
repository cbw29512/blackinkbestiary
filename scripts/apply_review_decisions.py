from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "test-gallery-state.json"
DECISIONS = ROOT / "review-previews" / "decisions.json"


def current_image_path(item: dict) -> Path:
    image_path = item.get("image_path")
    if image_path:
        return ROOT / "web" / str(image_path)
    return ROOT / "web" / "test-gallery" / f"{item.get('page_id')}-C{int(item.get('candidate') or 0):02d}.png"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def review_id_for(item: dict) -> str | None:
    path = current_image_path(item)
    if not path.exists():
        return None
    digest = sha256_file(path)
    return f"{item.get('page_id')}-C{int(item.get('candidate') or 0):02d}-H{digest[:16]}"


def main() -> int:
    if not DECISIONS.exists() or not STATE.exists():
        return 0

    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    reviews = decisions.get("reviews", [])
    changed = False
    applied = 0

    for review in reviews:
        target_review_id = str(review.get("review_id") or "")
        decision = str(review.get("decision") or "").lower()
        if not target_review_id or decision not in {"approve", "reject"}:
            continue

        for item in state.get("results", []):
            current_review_id = review_id_for(item)
            if current_review_id != target_review_id:
                continue

            notes = str(review.get("notes") or "")
            item["assistant_review"] = {
                "review_id": target_review_id,
                "decision": decision,
                "notes": notes,
            }

            if decision == "reject":
                item["status"] = "assistant_rejected"
                rejected_image = current_image_path(item)
                if rejected_image.exists():
                    rejected_image.unlink()
                selected = (state.get("selections") or {}).get(str(item.get("page_id")))
                if selected and int(selected.get("candidate") or 0) == int(item.get("candidate") or 0):
                    state["selections"].pop(str(item.get("page_id")), None)
            else:
                state.setdefault("selections", {})[str(item.get("page_id"))] = {
                    "candidate": int(item.get("candidate") or 0),
                    "source": "assistant_review",
                    "review_id": target_review_id,
                }

            changed = True
            applied += 1
            break

    if changed:
        STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print(f"Applied {applied} exact-image GitHub review decisions to local gallery state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
