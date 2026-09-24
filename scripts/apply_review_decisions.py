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


def classify_rejection_stage(review: dict) -> str:
    explicit = str(review.get("stage") or "").strip().lower()
    if explicit in {"identity", "environment", "action", "quality"}:
        return explicit

    notes = str(review.get("notes") or "").lower()
    identity_ok_phrases = (
        "anatomy is correct",
        "anatomy is usable",
        "anatomy is close",
        "anatomy looks correct",
        "creature anatomy is correct",
        "creature identity is correct",
        "identity is correct",
        "identity is usable",
    )
    identity_already_ok = any(phrase in notes for phrase in identity_ok_phrases)

    identity_terms = (
        "anatomy", "body plan", "body-plan", "dragonborn", "humanoid dragon",
        "extra arm", "extra arms", "separate humanoid arms", "too muscular",
        "bodybuilder", "gorilla", "ape", "wrong creature", "small wiry",
        "scale", "horn", "tail", "centipede has sparse", "leg pair",
    )
    environment_terms = (
        "environment", "habitat", "corridor", "hall", "stair", "spiral",
        "crawlway", "shaft", "catacomb", "arch", "stone hall", "mine",
        "web-filled dungeon", "does not read as",
    )
    action_terms = (
        "kicking", "kick", "wedged", "drag", "defending", "defend",
        "feeding", "offering", "signaling", "signal", "interaction",
        "contact", "recoil", "crawling", "story",
    )
    quality_terms = (
        "wallpaper", "dense web", "too dense", "border", "frame",
        "black fill", "grayscale", "clutter", "coloring", "negative space",
    )

    # Structural identity must be repaired first. Then setting geometry, then
    # action/contact, then print-quality cleanup.
    for stage, terms in (
        ("identity", identity_terms),
        ("environment", environment_terms),
        ("action", action_terms),
        ("quality", quality_terms),
    ):
        if stage == "identity" and identity_already_ok:
            continue
        if any(term in notes for term in terms):
            return stage
    return ""


def selection_eligible(item: dict) -> bool:
    return (
        str(item.get("status") or "") == "ready_for_review"
        and bool((item.get("visual_review") or {}).get("pass"))
    )


def selection_matches(state: dict, page_id: str, candidate_no: int, review_id: str) -> bool:
    selected = (state.get("selections") or {}).get(page_id) or {}
    return (
        int(selected.get("candidate") or 0) == candidate_no
        and str(selected.get("review_id") or "") == review_id
    )


def main() -> int:
    if not DECISIONS.exists() or not STATE.exists():
        return 0

    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    reviews = decisions.get("reviews", [])
    # Decisions are append-only history. Collapse duplicates so the latest
    # decision for an exact content hash wins deterministically.
    latest_by_review_id = {}
    for review in reviews:
        target_review_id = str(review.get("review_id") or "")
        decision = str(review.get("decision") or "").lower()
        if not target_review_id or decision not in {"approve", "reject", "select"}:
            continue
        latest_by_review_id[target_review_id] = review

    current_items = {}
    for item in state.get("results", []):
        current_review_id = review_id_for(item)
        if current_review_id:
            current_items[current_review_id] = item

    changed = False
    applied = 0

    for target_review_id, review in latest_by_review_id.items():
        item = current_items.get(target_review_id)
        if item is None:
            continue

        decision = str(review.get("decision") or "").lower()
        notes = str(review.get("notes") or "")
        stage = classify_rejection_stage(review) if decision == "reject" else ""
        next_review = {
            "review_id": target_review_id,
            "decision": decision,
            "notes": notes,
        }
        if stage:
            next_review["stage"] = stage
        page_id = str(item.get("page_id"))
        candidate_no = int(item.get("candidate") or 0)

        single_candidate_page = int(state.get("copies_per_page") or 1) <= 1
        decision_wants_selection = (
            decision == "select"
            or (decision == "approve" and single_candidate_page)
        )
        same_review = item.get("assistant_review") == next_review
        if same_review and not decision_wants_selection:
            continue
        if (
            same_review
            and decision_wants_selection
            and (
                not selection_eligible(item)
                or selection_matches(state, page_id, candidate_no, target_review_id)
            )
        ):
            continue

        item["assistant_review"] = next_review

        if decision == "reject":
            item["status"] = "assistant_rejected"
            rejected_image = current_image_path(item)
            if rejected_image.exists():
                rejected_image.unlink()
            selected = (state.get("selections") or {}).get(page_id)
            if selected and int(selected.get("candidate") or 0) == candidate_no:
                state["selections"].pop(page_id, None)
        elif decision == "select":
            # Exact-image selection is authoritative, but production selection
            # activates only after this same image passes the current local
            # staged reviewer. The decision remains attached to the image so a
            # later review recheck can activate it without asking again.
            if selection_eligible(item):
                state.setdefault("selections", {})[page_id] = {
                    "candidate": candidate_no,
                    "source": "assistant_selected",
                    "review_id": target_review_id,
                }
            else:
                selected = (state.get("selections") or {}).get(page_id)
                if selected and int(selected.get("candidate") or 0) == candidate_no:
                    state["selections"].pop(page_id, None)
        else:
            # Approval means this exact image is acceptable, but it must not
            # silently replace another final candidate merely because the
            # decision appeared later in the append-only review history.
            # On a one-candidate canary, approval acts as the selection only
            # after the current local staged reviewer also passes.
            selected = (state.get("selections") or {}).get(page_id)
            if (
                selected is None
                and single_candidate_page
                and selection_eligible(item)
            ):
                state.setdefault("selections", {})[page_id] = {
                    "candidate": candidate_no,
                    "source": "assistant_review",
                    "review_id": target_review_id,
                }

        changed = True
        applied += 1

    if changed:
        STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print(f"Applied {applied} exact-image GitHub review decisions to local gallery state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
