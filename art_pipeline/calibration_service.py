from __future__ import annotations
import json
import logging
import subprocess
import sys
import threading
from pathlib import Path
try:
    from .calibration_gate import calibration_paths, calibration_report, load_calibration_config
    from .local_preflight import local_generation_preflight
    from .page_contract import resolve_page_spec
    from .calibration_state import approve_calibration_candidate, load_calibration_state, reject_calibration_candidate, set_calibration_generation_error
except ImportError:
    from calibration_gate import calibration_paths, calibration_report, load_calibration_config
    from local_preflight import local_generation_preflight
    from page_contract import resolve_page_spec
    from calibration_state import approve_calibration_candidate, load_calibration_state, reject_calibration_candidate, set_calibration_generation_error
LOGGER = logging.getLogger(__name__)
_LOCK = threading.Lock()
_PROCESS: subprocess.Popen | None = None
_ACTIVE_PAGE_ID: str | None = None
def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not read calibration service JSON: %s", path)
        raise RuntimeError(f"Could not read calibration service JSON {path}: {exc}") from exc
def _worker_python(root: Path) -> str:
    local = root / ".blackink-tools" / "Scripts" / "python.exe"
    return str(local) if local.exists() else sys.executable
def calibration_worker_status() -> dict:
    global _PROCESS, _ACTIVE_PAGE_ID
    with _LOCK:
        process = _PROCESS
        if process is None:
            return {"running": False, "pid": None, "page_id": None}
        code = process.poll()
        if code is None:
            return {"running": True, "pid": process.pid, "page_id": _ACTIVE_PAGE_ID}
        page_id = _ACTIVE_PAGE_ID
        _PROCESS = None
        _ACTIVE_PAGE_ID = None
        return {"running": False, "pid": None, "page_id": page_id, "last_exit_code": code}
def public_calibration_state(root: Path) -> dict:
    config = load_calibration_config(root / "config" / "golden_five_calibration.json")
    paths = calibration_paths(root, config)
    state = load_calibration_state(root)
    manifest = _read_json(paths["manifest"])
    pages_by_id = {
        page["page_id"]: resolve_page_spec(page, root)
        for page in manifest.get("pages", [])
    }
    rows = []
    for case in config.get("cases", []):
        page_id = case["page_id"]
        page = pages_by_id[page_id]
        entry = state["pages"][page_id]
        rows.append({
            "page_id": page_id,
            "monster_name": page.get("monster_name"),
            "habitat": page.get("habitat"),
            "moment": page.get("moment"),
            "calibration_role": case.get("calibration_role"),
            "stress_test": case.get("stress_test") or [],
            "special_rule": case.get("special_rule"),
            "status": entry.get("status"),
            "attempt": entry.get("attempt", 0),
            "current_candidate": entry.get("current_candidate"),
            "approved_candidate": entry.get("approved_candidate"),
            "review_dimensions": entry.get("review_dimensions") or {},
            "review_notes": entry.get("review_notes"),
            "generation_error": entry.get("generation_error"),
        })
    return {
        "report": calibration_report(root),
        "worker": calibration_worker_status(),
        "required_review_dimensions": config.get("required_review_dimensions") or [],
        "pages": rows,
    }
def start_calibration_worker(root: Path, page_id: str) -> dict:
    global _PROCESS, _ACTIVE_PAGE_ID
    config = load_calibration_config(root / "config" / "golden_five_calibration.json")
    valid_ids = {item["page_id"] for item in config.get("cases", [])}
    if page_id not in valid_ids:
        raise ValueError(f"{page_id} is not a Golden Five calibration page")
    preflight = local_generation_preflight(root)
    if not preflight["ready_for_generation"]:
        return {"started": False, "running": False, "page_id": page_id,
                "reason": "local_generation_preflight_failed", "preflight": preflight}
    state = load_calibration_state(root)
    status = state["pages"][page_id].get("status")
    if status not in {"pending", "regenerate_requested"}:
        raise ValueError(f"{page_id} is not ready to generate: {status}")
    script = root / "scripts" / "generate_golden_page.py"
    if not script.exists():
        raise ValueError("Golden Five generator script is missing")
    set_calibration_generation_error(root, page_id, None)
    with _LOCK:
        if _PROCESS is not None and _PROCESS.poll() is None:
            return {"started": False, "running": True, "pid": _PROCESS.pid,
                    "page_id": _ACTIVE_PAGE_ID}
        log_path = root / "data" / "golden-five-worker.log"
        try:
            log = log_path.open("a", encoding="utf-8")
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
            _PROCESS = subprocess.Popen(
                [_worker_python(root), str(script), page_id],
                cwd=root,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
            log.close()
        except OSError as exc:
            LOGGER.exception("Could not start Golden Five worker for %s", page_id)
            raise RuntimeError(f"Could not start Golden Five worker: {exc}") from exc
        _ACTIVE_PAGE_ID = page_id
        return {"started": True, "running": True, "pid": _PROCESS.pid, "page_id": page_id}
def review_calibration(
    root: Path,
    page_id: str,
    decision: str,
    failed_dimensions: list[str] | None = None,
    notes: str = "",
) -> dict:
    try:
        if decision == "approve":
            return approve_calibration_candidate(root, page_id, notes)
        if decision == "reject":
            return reject_calibration_candidate(
                root,
                page_id,
                list(failed_dimensions or []),
                notes,
            )
        raise ValueError("Golden Five decision must be approve or reject")
    except (RuntimeError, ValueError):
        LOGGER.exception("Golden Five review failed for %s", page_id)
        raise
