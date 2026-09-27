from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config" / "golden_five_calibration.json"

LOGGER = logging.getLogger(__name__)

def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load Golden Five JSON: %s", path)
        raise RuntimeError(f"Could not load Golden Five JSON {path}: {exc}") from exc

def _write_json(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        LOGGER.exception("Could not write Golden Five JSON: %s", path)
        raise RuntimeError(f"Could not write Golden Five JSON {path}: {exc}") from exc

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_calibration_config(path: Path = CONFIG_FILE) -> dict:
    return _read_json(path)

def calibration_paths(root: Path = ROOT, config: dict | None = None) -> dict[str, Path]:
    cfg = config or load_calibration_config(root / "config" / "golden_five_calibration.json")
    return {
        "manifest": root / cfg["source_manifest"],
        "state": root / cfg["state_path"],
        "output_dir": root / cfg["output_dir"],
    }

def calibration_case(page_id: str, config: dict | None = None) -> dict:
    cfg = config or load_calibration_config()
    wanted = str(page_id or "").strip()
    match = next((item for item in cfg.get("cases", []) if item.get("page_id") == wanted), None)
    if not match:
        raise RuntimeError(f"{wanted!r} is not a Golden Five calibration page")
    return dict(match)

def validate_calibration(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    cfg = load_calibration_config(root / "config" / "golden_five_calibration.json")
    paths = calibration_paths(root, cfg)
    manifest = _read_json(paths["manifest"])
    state = _read_json(paths["state"])
    quality = _read_json(root / "config" / "quality_rules.json")

    case_ids = [str(item.get("page_id") or "").strip() for item in cfg.get("cases", [])]
    manifest_ids = {item.get("page_id") for item in manifest.get("pages", [])}
    required_dimensions = list(cfg.get("required_review_dimensions") or [])
    valid_dimensions = set(quality.get("review_dimensions") or [])

    if len(case_ids) != 5 or len(set(case_ids)) != 5:
        errors.append("Golden Five must contain exactly five unique page IDs")
    for page_id in case_ids:
        if page_id not in manifest_ids:
            errors.append(f"{page_id}: calibration page missing from source manifest")
        if page_id not in (state.get("pages") or {}):
            errors.append(f"{page_id}: calibration page missing from calibration state")
    if set(state.get("pages") or {}) != set(case_ids):
        errors.append("calibration state page IDs must exactly match Golden Five cases")
    unknown = sorted(set(required_dimensions) - valid_dimensions)
    if unknown:
        errors.append("unknown calibration review dimensions: " + ", ".join(unknown))

    for case in cfg.get("cases", []):
        page_id = case.get("page_id")
        if not case.get("calibration_role"):
            errors.append(f"{page_id}: calibration_role is required")
        if not case.get("stress_test"):
            errors.append(f"{page_id}: stress_test is required")
        if not case.get("special_rule"):
            errors.append(f"{page_id}: special_rule is required")

    return errors

def calibration_report(root: Path = ROOT) -> dict:
    cfg = load_calibration_config(root / "config" / "golden_five_calibration.json")
    paths = calibration_paths(root, cfg)
    state = _read_json(paths["state"])
    required = list(cfg.get("required_review_dimensions") or [])
    rows = []
    approved = 0

    for case in cfg.get("cases", []):
        page_id = case["page_id"]
        entry = state["pages"][page_id]
        dimensions = entry.get("review_dimensions") or {}
        all_dimensions_pass = all(dimensions.get(name) is True for name in required)
        locked = entry.get("status") == "locked"
        passed = locked and all_dimensions_pass and bool(entry.get("approved_candidate"))
        approved += int(passed)
        rows.append({
            "page_id": page_id,
            "status": entry.get("status"),
            "attempt": entry.get("attempt", 0),
            "all_dimensions_pass": all_dimensions_pass,
            "approved": passed,
        })

    required_count = int((cfg.get("production_gate") or {}).get("required_approved_pages", 5))
    return {
        "pass": not validate_calibration(root),
        "calibration_id": cfg.get("calibration_id"),
        "source_manifest": cfg.get("source_manifest"),
        "approved": approved,
        "required": required_count,
        "production_calibrated": approved >= required_count,
        "pages": rows,
    }

def save_calibration_state(state: dict, root: Path = ROOT) -> None:
    cfg = load_calibration_config(root / "config" / "golden_five_calibration.json")
    state["updated_at"] = utc_now()
    state["complete"] = calibration_report_from_state(state, cfg)
    _write_json(calibration_paths(root, cfg)["state"], state)

def calibration_report_from_state(state: dict, config: dict) -> bool:
    required = list(config.get("required_review_dimensions") or [])
    required_count = int((config.get("production_gate") or {}).get("required_approved_pages", 5))
    approved = 0
    for case in config.get("cases", []):
        entry = (state.get("pages") or {}).get(case["page_id"], {})
        dimensions = entry.get("review_dimensions") or {}
        if (
            entry.get("status") == "locked"
            and entry.get("approved_candidate")
            and all(dimensions.get(name) is True for name in required)
        ):
            approved += 1
    return approved >= required_count
