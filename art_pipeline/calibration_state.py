from __future__ import annotations

import json
import logging
from pathlib import Path

try:
    from .calibration_gate import (
        calibration_case,
        calibration_paths,
        load_calibration_config,
        save_calibration_state,
        utc_now,
    )
except ImportError:
    from calibration_gate import (
        calibration_case,
        calibration_paths,
        load_calibration_config,
        save_calibration_state,
        utc_now,
    )

LOGGER = logging.getLogger(__name__)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not read calibration state: %s", path)
        raise RuntimeError(f"Could not read calibration state {path}: {exc}") from exc


def load_calibration_state(root: Path) -> dict:
    cfg = load_calibration_config(root / "config" / "golden_five_calibration.json")
    return _read_json(calibration_paths(root, cfg)["state"])


def register_calibration_candidate(
    root: Path,
    page_id: str,
    image_path: str,
    source: dict | None = None,
) -> dict:
    cfg = load_calibration_config(root / "config" / "golden_five_calibration.json")
    calibration_case(page_id, cfg)
    state = load_calibration_state(root)
    entry = state["pages"][page_id]
    attempt = int(entry.get("attempt", 0)) + 1
    candidate = {
        "candidate_id": f"{page_id}-GOLDEN-A{attempt:03d}",
        "attempt": attempt,
        "image_path": image_path,
        "source": source or {},
        "created_at": utc_now(),
    }
    entry["attempt"] = attempt
    entry["current_candidate"] = candidate
    entry["status"] = "awaiting_human"
    entry.pop("generation_error", None)
    entry.setdefault("attempt_history", []).append(candidate)
    save_calibration_state(state, root)
    return candidate


def set_calibration_generation_error(
    root: Path,
    page_id: str,
    message: str | None,
) -> dict:
    state = load_calibration_state(root)
    if page_id not in state.get("pages", {}):
        raise RuntimeError(f"{page_id} is not in Golden Five calibration state")
    entry = state["pages"][page_id]
    if message:
        entry["generation_error"] = {"message": str(message), "at": utc_now()}
    else:
        entry.pop("generation_error", None)
    save_calibration_state(state, root)
    return entry


def approve_calibration_candidate(root: Path, page_id: str, notes: str = "") -> dict:
    cfg = load_calibration_config(root / "config" / "golden_five_calibration.json")
    calibration_case(page_id, cfg)
    state = load_calibration_state(root)
    entry = state["pages"][page_id]
    candidate = entry.get("current_candidate")
    if not candidate or entry.get("status") != "awaiting_human":
        raise RuntimeError(f"{page_id} must have a candidate awaiting human review")

    entry["status"] = "locked"
    entry["approved_candidate"] = candidate
    entry["review_dimensions"] = {
        name: True for name in cfg.get("required_review_dimensions", [])
    }
    entry["review_notes"] = {"decision": "approve", "text": notes.strip(), "at": utc_now()}
    save_calibration_state(state, root)
    return entry


def reject_calibration_candidate(
    root: Path,
    page_id: str,
    failed_dimensions: list[str],
    notes: str = "",
) -> dict:
    cfg = load_calibration_config(root / "config" / "golden_five_calibration.json")
    calibration_case(page_id, cfg)
    required = set(cfg.get("required_review_dimensions") or [])
    failed = {str(item).strip() for item in failed_dimensions if str(item).strip()}
    unknown = sorted(failed - required)
    if unknown:
        raise RuntimeError("Unknown review dimensions: " + ", ".join(unknown))
    if not failed:
        raise RuntimeError("Reject requires at least one failed review dimension")

    state = load_calibration_state(root)
    entry = state["pages"][page_id]
    if not entry.get("current_candidate"):
        raise RuntimeError(f"{page_id} has no calibration candidate to reject")

    entry["status"] = "regenerate_requested"
    entry["review_dimensions"] = {name: name not in failed for name in required}
    entry["review_notes"] = {
        "decision": "reject",
        "failed_dimensions": sorted(failed),
        "preserve_dimensions": sorted(required - failed),
        "text": notes.strip(),
        "at": utc_now(),
    }
    save_calibration_state(state, root)
    return entry
