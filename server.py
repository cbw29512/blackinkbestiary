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
from art_pipeline.manifest_validation import validate_manifest
from art_pipeline.monster_catalog import load_monster_for_page
from art_pipeline.quality_system import expand_defect_tags, recommended_action
from art_pipeline.studio_config import active_book_paths
from art_pipeline.state_validation import ACTIVE_STATES, assert_valid_state

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
_GENERATION_LOCK = threading.Lock()
_GENERATION_PROCESS = None

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
    return tome


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
        "current_state": state["pages"][state["current_page_id"]],
        "current_page_id": state["current_page_id"],
        "generation_worker": generation_worker_status(),
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
    route = recommended_action(ROOT, quick_tags) if quick_tags else decision
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
            if path == "/api/generation-status":
                self.send_json(generation_worker_status())
                return
            self.serve_static(path)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self.read_body_json()
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
            if path == "/api/generate":
                worker = start_generation_worker()
                result = public_state()
                result["generation_worker"] = worker
                self.send_json(result)
                return
            if path == "/api/candidate":
                self.send_json(register_candidate(payload))
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
    validate_state(load_tome(), load_state())
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
