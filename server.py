from __future__ import annotations

import argparse
import filecmp
import json
import mimetypes
import shutil
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from art_pipeline.rebuild_state import activate_rebuild_source
from art_pipeline.calibration_gate import calibration_report
from art_pipeline.local_preflight import local_generation_preflight
from art_pipeline.calibration_service import (
    public_calibration_state,
    review_calibration,
    start_calibration_worker,
)
from art_pipeline.manifest_validation import validate_manifest
from art_pipeline.page_contract import resolve_manifest
from art_pipeline.environment_catalog import resolve_environment_profile
from art_pipeline.monster_catalog import load_monster_for_page
from art_pipeline.quality_system import expand_defect_tags, review_diagnosis
from art_pipeline.studio_config import active_book_paths
from art_pipeline.state_validation import ACTIVE_STATES, assert_valid_state
from art_pipeline.autopilot_status import public_autopilot_status
from art_pipeline.human_review import (
    REVIEWABLE_STATUSES as HUMAN_REVIEWABLE_STATUSES,
    append_human_decision,
    configured_canary_ids,
    current_image_path as human_current_image_path,
    exact_review_id as human_exact_review_id,
)
from art_pipeline.learning_feedback import human_feedback_summary
from art_pipeline.review_authority import decision_is_authoritative

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"
_BOOK_PATHS = active_book_paths(ROOT)
TOME_FILE = _BOOK_PATHS["manifest"]
STATE_FILE = _BOOK_PATHS["state"]
REVIEWS_FILE = _BOOK_PATHS["reviews"]
APPROVED_ROOT = WEB_DIR / "approved"
MONSTER_DIR = DATA_DIR / "monsters"
GENERATOR_SCRIPT = ROOT / "scripts" / "generate_current_page.py"
GENERATOR_LOG = DATA_DIR / "generation-worker.log"
TEST_GALLERY_STATE = DATA_DIR / "test-gallery-state.json"
_GENERATION_LOCK = threading.Lock()
_GENERATION_PROCESS = None
QUALITY_CURRENT = ROOT / "review-previews" / "quality-current.json"
REVIEW_DECISIONS = ROOT / "review-previews" / "decisions.json"
QUALITY_SCORECARD = ROOT / "config" / "quality_scorecard.json"
LOCAL_ONLY_HOSTS = {"127.0.0.1", "localhost", "::1"}

VALID_DECISIONS = {"approve", "modify", "regenerate"}
GENERATABLE_STATES = {"queued", "modify_requested", "regenerate_requested", "generation_failed"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_tome():
    tome = read_json(TOME_FILE)
    errors = validate_manifest(ROOT, tome, MONSTER_DIR)
    if errors:
        raise ValueError("Production manifest invalid: " + " | ".join(errors))
    return resolve_manifest(tome, ROOT)


def load_state():
    return read_json(STATE_FILE)


def page_by_id(tome, page_id: str):
    return next((page for page in tome["pages"] if page["page_id"] == page_id), None)


def load_monster_spec(page: dict):
    return load_monster_for_page(page, MONSTER_DIR)

def public_monster_spec(page: dict):
    spec = load_monster_spec(page)
    if not spec:
        return None
    payload = json.loads(json.dumps(spec))
    reference = payload.get("reference") or {}
    image = str(reference.get("image") or "").strip()
    resolved = None
    if image:
        relative = Path(image)
        if not relative.is_absolute() and ".." not in relative.parts:
            target = (WEB_DIR / relative).resolve()
            web_root = WEB_DIR.resolve()
            if target.exists() and target.is_file() and (target == web_root or web_root in target.parents):
                resolved = relative.as_posix()
    reference["resolved_image"] = resolved
    payload["reference"] = reference
    return payload


def public_environment_profile(page: dict):
    profile_id = str(page.get("environment_profile_id") or "").strip()
    if not profile_id:
        return None
    return resolve_environment_profile(profile_id)


def active_page_ids(state):
    return [pid for pid, entry in state["pages"].items() if entry["status"] in ACTIVE_STATES]


def validate_state(tome, state):
    assert_valid_state(tome, state)

def comfy_health():
    url = "http://127.0.0.1:8188/system_stats"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        devices = []
        for device in payload.get("devices", []):
            devices.append({
                "name": device.get("name"),
                "type": device.get("type"),
                "vram_total": device.get("vram_total"),
                "vram_free": device.get("vram_free"),
            })
        return {"connected": True, "url": "http://127.0.0.1:8188", "devices": devices}
    except Exception as exc:
        return {"connected": False, "url": "http://127.0.0.1:8188", "error": str(exc)}


def worker_python() -> str:
    local = ROOT / ".blackink-tools" / "Scripts" / "python.exe"
    return str(local) if local.exists() else sys.executable


def generation_worker_status():
    global _GENERATION_PROCESS
    with _GENERATION_LOCK:
        process = _GENERATION_PROCESS
        if process is None:
            return {"running": False, "pid": None}
        code = process.poll()
        if code is None:
            return {"running": True, "pid": process.pid}
        _GENERATION_PROCESS = None
        return {"running": False, "pid": None, "last_exit_code": code}


def start_generation_worker():
    global _GENERATION_PROCESS
    state = load_state()
    tome = load_tome()
    page_id = state["current_page_id"]
    page = page_by_id(tome, page_id)
    status = state["pages"][page_id]["status"]
    if status not in GENERATABLE_STATES:
        raise ValueError(f"Current page is not ready to generate: {status}")
    if not page or not page.get("monster_spec_id"):
        return {
            "started": False,
            "running": False,
            "page_id": page_id,
            "reason": "canonical_monster_spec_required",
        }
    if not GENERATOR_SCRIPT.exists():
        raise ValueError("Generation worker script is missing")

    first_page_id = tome["pages"][0]["page_id"]
    calibration = calibration_report(ROOT)
    if page_id != first_page_id and not calibration["production_calibrated"]:
        return {
            "started": False,
            "running": False,
            "page_id": page_id,
            "reason": "golden_five_calibration_required",
            "calibration": calibration,
        }

    preflight = local_generation_preflight(ROOT)
    if not preflight["ready_for_generation"]:
        return {
            "started": False,
            "running": False,
            "page_id": page_id,
            "reason": "local_generation_preflight_failed",
            "preflight": preflight,
        }

    with _GENERATION_LOCK:
        if _GENERATION_PROCESS is not None and _GENERATION_PROCESS.poll() is None:
            return {"started": False, "running": True, "pid": _GENERATION_PROCESS.pid}

        GENERATOR_LOG.parent.mkdir(parents=True, exist_ok=True)
        log = GENERATOR_LOG.open("a", encoding="utf-8")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        process = subprocess.Popen(
            [worker_python(), str(GENERATOR_SCRIPT)],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        log.close()
        _GENERATION_PROCESS = process
        return {"started": True, "running": True, "pid": process.pid, "page_id": page_id}


def public_state():
    tome = load_tome()
    state = load_state()
    validate_state(tome, state)
    current = page_by_id(tome, state["current_page_id"])
    approved = sum(1 for page in state["pages"].values() if page["status"] == "locked")
    return {
        "tome": {
            "tome_id": tome["tome_id"],
            "title": tome["title"],
            "theme": tome["theme"],
            "total_pages": tome["total_pages"],
        },
        "progress": {"approved": approved, "total": tome["total_pages"]},
        "current_page": current,
        "current_monster_spec": public_monster_spec(current),
        "current_environment_profile": public_environment_profile(current),
        "current_state": state["pages"][state["current_page_id"]],
        "current_page_id": state["current_page_id"],
        "generation_worker": generation_worker_status(),
        "golden_five_calibration": calibration_report(ROOT),
        "ordered_pages": [
            {
                "page_id": page["page_id"],
                "monster_name": page["monster_name"],
                "status": state["pages"][page["page_id"]]["status"],
                "approved_image_path": state["pages"][page["page_id"]].get("approved_image_path"),
            }
            for page in tome["pages"]
        ],
    }


def append_review(entry):
    REVIEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REVIEWS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")



def tome_folder_name(tome) -> str:
    tome_id = str(tome.get("tome_id", "TOME-I")).strip()
    if tome_id.upper().startswith("TOME-"):
        return "Tome-" + tome_id.split("-", 1)[1]
    return tome_id or "Tome-I"


def archive_approved_candidate(tome, page_id: str, candidate: dict) -> str:
    image_path = str(candidate.get("image_path", "")).strip()
    if not image_path:
        raise ValueError("Candidate has no image_path")

    relative = Path(image_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Candidate image_path must stay inside the Studio web folder")

    source = (WEB_DIR / relative).resolve()
    web_root = WEB_DIR.resolve()
    if source != web_root and web_root not in source.parents:
        raise ValueError("Candidate image is outside the Studio web folder")
    if not source.exists() or not source.is_file():
        raise ValueError(f"Candidate image file does not exist: {image_path}")
    if source.suffix.lower() != ".png":
        raise ValueError("Approved production pages must be PNG files")

    destination_dir = APPROVED_ROOT / tome_folder_name(tome)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{page_id}.png"

    if destination.exists():
        if not filecmp.cmp(source, destination, shallow=False):
            raise ValueError(
                f"Approved page already exists with different artwork: "
                f"{destination.relative_to(WEB_DIR).as_posix()}"
            )
    else:
        shutil.copy2(source, destination)

    return destination.relative_to(WEB_DIR).as_posix()


def apply_decision(decision: str, notes: str = "", quick_tags=None):
    if decision not in VALID_DECISIONS:
        raise ValueError("Invalid decision")
    quick_tags = list(quick_tags or [])
    requested_decision = decision
    diagnosis = review_diagnosis(ROOT, quick_tags) if quick_tags else {
        "action": decision,
        "failed_dimensions": [],
        "preserve_dimensions": [],
        "unknown_tags": [],
    }
    route = diagnosis["action"]
    if decision == "modify" and route == "regenerate":
        decision = "regenerate"
    tome = load_tome()
    state = load_state()
    validate_state(tome, state)
    page_id = state["current_page_id"]
    page_state = state["pages"][page_id]
    candidate = page_state.get("current_candidate")

    if decision == "approve":
        if not candidate:
            raise ValueError("Cannot approve without a current candidate")
        if page_state["status"] != "awaiting_human":
            raise ValueError("Page must be awaiting human review before approval")
        approved_image_path = archive_approved_candidate(tome, page_id, candidate)
        page_state["status"] = "locked"
        page_state["approved_candidate"] = candidate
        page_state["approved_image_path"] = approved_image_path
        page_state["approved_at"] = utc_now()
        page_state["last_decision"] = "approve"

        order = [page["page_id"] for page in tome["pages"]]
        index = order.index(page_id)
        if index + 1 < len(order):
            next_id = order[index + 1]
            state["current_page_id"] = next_id
            if not activate_rebuild_source(state, next_id, WEB_DIR):
                state["pages"][next_id]["status"] = "queued"
        else:
            state["complete"] = True
    else:
        page_state["status"] = "modify_requested" if decision == "modify" else "regenerate_requested"
        page_state["last_decision"] = decision
        page_state["review_notes"] = {
            "text": notes.strip(),
            "quick_tags": quick_tags,
            "routing_recommendation": route,
            "failed_dimensions": diagnosis["failed_dimensions"],
            "preserve_dimensions": diagnosis["preserve_dimensions"],
            "unknown_tags": diagnosis["unknown_tags"],
            "at": utc_now(),
        }

    state["updated_at"] = utc_now()
    page = page_by_id(tome, page_id) or {}
    append_review({
        "book_id": tome.get("tome_id"),
        "book_title": tome.get("title"),
        "page_id": page_id,
        "monster_name": page.get("monster_name"),
        "archetype": page.get("archetype"),
        "requested_decision": requested_decision,
        "decision": decision,
        "routing_recommendation": route,
        "failed_dimensions": diagnosis["failed_dimensions"],
        "preserve_dimensions": diagnosis["preserve_dimensions"],
        "unknown_tags": diagnosis["unknown_tags"],
        "candidate": candidate,
        "approved_image_path": page_state.get("approved_image_path"),
        "notes": notes.strip(),
        "quick_tags": quick_tags,
        "remediation_directives": expand_defect_tags(ROOT, quick_tags),
        "timestamp": utc_now(),
    })
    write_json(STATE_FILE, state)
    return public_state()


def register_candidate(payload):
    tome = load_tome()
    state = load_state()
    validate_state(tome, state)
    page_id = payload.get("page_id")
    if page_id != state["current_page_id"]:
        raise ValueError("Candidate can only be registered for the current page")

    image_path = str(payload.get("image_path", "")).strip()
    if not image_path:
        raise ValueError("image_path is required")
    if image_path.startswith("/") or ".." in Path(image_path).parts:
        raise ValueError("image_path must be a relative safe path")

    page_state = state["pages"][page_id]
    attempt = int(page_state.get("attempt", 0)) + 1
    candidate = {
        "candidate_id": payload.get("candidate_id") or f"{page_id}-A{attempt:03d}",
        "attempt": attempt,
        "image_path": image_path,
        "qa_status": payload.get("qa_status", "pass"),
        "supervisor_status": payload.get("supervisor_status", "ready_for_human"),
        "generation_mode": payload.get("generation_mode", "unknown"),
        "technical_retry": int(payload.get("technical_retry", 0)),
        "source": payload.get("source"),
        "created_at": utc_now(),
    }
    page_state["attempt"] = attempt
    page_state["current_candidate"] = candidate
    page_state.setdefault("attempt_history", []).append(candidate)
    page_state["status"] = "awaiting_human"
    state["updated_at"] = utc_now()
    write_json(STATE_FILE, state)
    return public_state()



def current_engine_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="strict",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        return "unknown"


def _safe_image_url(item: dict) -> str | None:
    path = human_current_image_path(ROOT, item)
    try:
        resolved = path.resolve()
        web_root = WEB_DIR.resolve()
    except OSError:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    if resolved != web_root and web_root not in resolved.parents:
        return None
    return "/" + resolved.relative_to(web_root).as_posix()


def _human_decision_history() -> dict[str, list[dict]]:
    if not REVIEW_DECISIONS.exists():
        return {}
    try:
        payload = read_json(REVIEW_DECISIONS)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    rows: dict[str, list[dict]] = {}
    for review in payload.get("reviews", []):
        if str(review.get("reviewer") or "").strip().lower() != "human":
            continue
        page_id = str(review.get("page_id") or "").strip()
        if not page_id:
            continue
        rows.setdefault(page_id, []).append({
            "decision": review.get("decision"),
            "stage": review.get("stage"),
            "notes": review.get("notes"),
            "decided_at": review.get("decided_at"),
            "review_id": review.get("review_id"),
        })
    return rows


def _human_review_pages() -> list[dict]:
    canary_ids = configured_canary_ids(ROOT)
    state = read_json(TEST_GALLERY_STATE) if TEST_GALLERY_STATE.exists() else {"results": []}
    latest: dict[str, dict] = {}
    for item in state.get("results", []):
        page_id = str(item.get("page_id") or "")
        if page_id in canary_ids and int(item.get("candidate") or 0) == 1:
            latest[page_id] = item

    contexts = {}
    try:
        tome = load_tome()
        contexts = {str(page.get("page_id") or ""): page for page in tome.get("pages", [])}
    except Exception:
        contexts = {}

    history = _human_decision_history()
    pages = []
    for page_id in canary_ids:
        item = latest.get(page_id) or {}
        page = contexts.get(page_id) or {}
        assistant = item.get("assistant_review") or {}
        status = str(item.get("status") or "missing")
        review_id = None
        if item:
            try:
                review_id = human_exact_review_id(ROOT, item)
            except ValueError:
                review_id = None
        authoritative = bool(item) and decision_is_authoritative(assistant, ROOT)
        decision = str(assistant.get("decision") or "").strip().lower()
        approved = bool(
            authoritative
            and decision in {"approve", "select"}
            and review_id
            and str(assistant.get("review_id") or "").strip() == review_id
        )
        reviewable = bool(
            item
            and status in HUMAN_REVIEWABLE_STATUSES
            and review_id
            and not approved
        )
        needs_generation = status in {
            "assistant_rejected",
            "failed",
            "technical_qa_failed",
            "vision_reviewer_failed",
            "semantic_stalled",
        }
        advisory = item.get("visual_review") or {}
        pages.append({
            "page_id": page_id,
            "monster_name": item.get("monster_name") or page.get("monster_name"),
            "candidate": int(item.get("candidate") or 1),
            "status": status,
            "review_id": review_id,
            "image_url": _safe_image_url(item) if item else None,
            "human_approved": approved,
            "awaiting_human": reviewable,
            "needs_generation": needs_generation,
            "habitat": page.get("habitat"),
            "story_moment": page.get("moment"),
            "must_include": page.get("must_include") or [],
            "identity_rules": page.get("identity_rules") or [],
            "advisory": {
                "stage": advisory.get("stage"),
                "score": advisory.get("score"),
                "pass": bool(advisory.get("pass")),
                "defects": advisory.get("defects") or [],
                "preserve": advisory.get("preserve") or [],
            },
            "human_history": (history.get(page_id) or [])[-5:],
        })
    return pages


def public_human_review() -> dict:
    pages = _human_review_pages()
    scorecard = read_json(QUALITY_SCORECARD)
    quality = {}
    if QUALITY_CURRENT.exists():
        try:
            quality = read_json(QUALITY_CURRENT)
        except (OSError, ValueError, json.JSONDecodeError):
            quality = {}

    engine = current_engine_commit()
    expected_contract = str(scorecard.get("contract_version") or "")
    measured_contract = str(quality.get("quality_contract_version") or "")
    quality_engine = str(quality.get("engine_commit") or "")
    score_stale = bool(
        not quality
        or measured_contract != expected_contract
        or (engine != "unknown" and quality_engine and quality_engine != engine)
    )

    try:
        autopilot = public_autopilot_status()
    except Exception as exc:
        autopilot = {"error": str(exc)}

    return {
        "schema_version": 1,
        "local_only": True,
        "engine_commit": engine,
        "quality_contract_version": expected_contract,
        "human_approved": sum(1 for page in pages if page["human_approved"]),
        "awaiting_human": sum(1 for page in pages if page["awaiting_human"]),
        "needs_generation": sum(1 for page in pages if page["needs_generation"]),
        "canary_total": len(pages),
        "quality": {
            "overall_automated_readiness": quality.get("overall_automated_readiness"),
            "readiness_floor": quality.get("readiness_floor"),
            "series_score": quality.get("series_score"),
            "metrics": quality.get("metrics") or {},
            "known_blockers": quality.get("known_blockers") or [],
            "measured_at": quality.get("measured_at"),
            "measured_engine_commit": quality_engine or None,
            "measured_contract_version": measured_contract or None,
            "stale": score_stale,
        },
        "human_feedback": human_feedback_summary(ROOT),
        "autopilot": autopilot,
        "pages": pages,
    }


def apply_human_review_from_web(payload: dict) -> dict:
    page_id = str(payload.get("page_id") or "").strip()
    candidate = int(payload.get("candidate") or 0)
    supplied_review_id = str(payload.get("review_id") or "").strip()
    decision = str(payload.get("decision") or "").strip().lower()
    stage = str(payload.get("stage") or "").strip().lower()
    notes = str(payload.get("notes") or "").strip()

    if page_id not in configured_canary_ids(ROOT):
        raise ValueError("Unknown Canary page.")
    if candidate < 1:
        raise ValueError("Candidate number is required.")

    state = read_json(TEST_GALLERY_STATE) if TEST_GALLERY_STATE.exists() else {"results": []}
    match = None
    for item in state.get("results", []):
        if (
            str(item.get("page_id") or "") == page_id
            and int(item.get("candidate") or 0) == candidate
        ):
            match = item
    if match is None:
        raise ValueError("Current Canary candidate was not found.")
    if str(match.get("status") or "") not in HUMAN_REVIEWABLE_STATUSES:
        raise ValueError("This Canary is no longer awaiting human review.")

    current_review_id = human_exact_review_id(ROOT, match)
    if not supplied_review_id or supplied_review_id != current_review_id:
        raise ValueError(
            "This image changed after the page loaded. Refresh before making a decision."
        )

    row = append_human_decision(
        ROOT,
        match,
        decision=decision,
        notes=notes,
        stage=stage,
    )

    subprocess.run(
        [worker_python(), str(ROOT / "scripts" / "apply_review_decisions.py")],
        cwd=ROOT,
        check=True,
    )
    publish = subprocess.run(
        [worker_python(), str(ROOT / "scripts" / "publish_review_previews.py")],
        cwd=ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    result = public_human_review()
    result["saved_decision"] = row
    result["published"] = publish.returncode == 0
    if publish.returncode != 0:
        detail = (publish.stderr or publish.stdout or "").strip().splitlines()
        result["publish_warning"] = detail[-1] if detail else "Review snapshot publish failed; the local decision is still saved."
    return result


def assert_local_only_host(host: str) -> None:
    if str(host or "").strip().lower() not in LOCAL_ONLY_HOSTS:
        raise ValueError(
            "Black-Ink review Studio is local-only. Bind to 127.0.0.1, localhost, or ::1."
        )


class Handler(BaseHTTPRequestHandler):
    server_version = "BlackInkBestiary/0.1"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_body_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("Request too large")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/health":
                self.send_json({"ok": True, "time": utc_now()})
                return
            if path == "/api/state":
                self.send_json(public_state())
                return
            if path == "/api/comfy-health":
                self.send_json(comfy_health())
                return
            if path == "/api/local-preflight":
                self.send_json(local_generation_preflight(ROOT))
                return
            if path == "/api/generation-status":
                self.send_json(generation_worker_status())
                return
            if path == "/api/autopilot-status":
                self.send_json(public_autopilot_status())
                return
            if path == "/api/human-review":
                self.send_json(public_human_review())
                return
            if path == "/api/test-gallery":
                self.send_json(read_json(TEST_GALLERY_STATE) if TEST_GALLERY_STATE.exists() else {"results": []})
                return
            if path == "/api/golden-five":
                self.send_json(public_calibration_state(ROOT))
                return
            self.serve_static(path)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self.read_body_json()
            if path == "/api/human-review/decision":
                self.send_json(apply_human_review_from_web(payload))
                return
            if path == "/api/decision":
                decision = payload.get("decision", "")
                result = apply_decision(
                    decision,
                    payload.get("notes", ""),
                    payload.get("quick_tags", []),
                )
                if decision in VALID_DECISIONS and result["current_state"]["status"] in GENERATABLE_STATES:
                    result["generation_worker"] = start_generation_worker()
                self.send_json(result)
                return
            if path == "/api/test-gallery/select":
                if not TEST_GALLERY_STATE.exists():
                    raise ValueError("Test gallery has not been generated")
                gallery = read_json(TEST_GALLERY_STATE)
                page_id = str(payload.get("page_id") or "").strip()
                candidate = int(payload.get("candidate") or 0)
                match = next((item for item in gallery.get("results", []) if item.get("page_id") == page_id and int(item.get("candidate") or 0) == candidate and item.get("status") == "ready_for_review"), None)
                if not match:
                    raise ValueError("Selected test candidate was not found or did not pass technical QA")
                gallery.setdefault("selections", {})[page_id] = {
                    "candidate": candidate,
                    "image_path": match.get("image_path"),
                    "seed": match.get("seed"),
                    "selected_at": utc_now(),
                }
                gallery["updated_at"] = utc_now()
                write_json(TEST_GALLERY_STATE, gallery)
                self.send_json(gallery)
                return
            if path == "/api/generate":
                worker = start_generation_worker()
                result = public_state()
                result["generation_worker"] = worker
                self.send_json(result)
                return
            if path == "/api/candidate":
                self.send_json(register_candidate(payload))
                return
            if path == "/api/golden-five/generate":
                page_id = str(payload.get("page_id") or "").strip()
                worker = start_calibration_worker(ROOT, page_id)
                result = public_calibration_state(ROOT)
                result["worker"] = worker
                self.send_json(result)
                return
            if path == "/api/golden-five/review":
                page_id = str(payload.get("page_id") or "").strip()
                decision = str(payload.get("decision") or "").strip()
                review_calibration(
                    ROOT,
                    page_id,
                    decision,
                    payload.get("failed_dimensions") or [],
                    str(payload.get("notes") or ""),
                )
                self.send_json(public_calibration_state(ROOT))
                return
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def serve_static(self, request_path: str):
        rel = unquote(request_path.lstrip("/")) or "index.html"
        target = (WEB_DIR / rel).resolve()
        if WEB_DIR.resolve() not in target.parents and target != WEB_DIR.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = target.read_bytes()
        mime, _ = mimetypes.guess_type(target.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)


def run(host="127.0.0.1", port=8765, open_browser=True):
    assert_local_only_host(host)
    # Keep the review/health server available even when unrelated production
    # state is temporarily invalid; stateful API routes validate on access.
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"Black-Ink Bestiary Studio: {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Black-Ink Bestiary local production studio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    run(args.host, args.port, not args.no_browser)
