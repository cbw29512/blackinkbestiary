from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"
TOME_FILE = DATA_DIR / "tome-I.json"
STATE_FILE = DATA_DIR / "production-state.json"
REVIEWS_FILE = DATA_DIR / "reviews.jsonl"

VALID_DECISIONS = {"approve", "modify", "regenerate"}
ACTIVE_STATES = {
    "queued", "generating", "qa_review", "supervisor_review",
    "awaiting_human", "modify_requested", "regenerate_requested",
}


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
    return read_json(TOME_FILE)


def load_state():
    return read_json(STATE_FILE)


def page_by_id(tome, page_id: str):
    return next((page for page in tome["pages"] if page["page_id"] == page_id), None)


def active_page_ids(state):
    return [pid for pid, entry in state["pages"].items() if entry["status"] in ACTIVE_STATES]


def validate_state(tome, state):
    ids = [p["page_id"] for p in tome["pages"]]
    if len(ids) != tome["total_pages"]:
        raise ValueError("Manifest page count does not match total_pages")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate page IDs in manifest")
    if state["current_page_id"] not in ids:
        raise ValueError("Current page is not in the manifest")
    if set(state["pages"].keys()) != set(ids):
        raise ValueError("Production state page IDs do not match manifest")
    active = active_page_ids(state)
    if len(active) > 1:
        raise ValueError(f"More than one active page: {active}")
    if active and active[0] != state["current_page_id"]:
        raise ValueError("Active page does not match current_page_id")


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
        "current_state": state["pages"][state["current_page_id"]],
        "current_page_id": state["current_page_id"],
        "ordered_pages": [
            {
                "page_id": page["page_id"],
                "monster_name": page["monster_name"],
                "status": state["pages"][page["page_id"]]["status"],
            }
            for page in tome["pages"]
        ],
    }


def append_review(entry):
    REVIEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REVIEWS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def apply_decision(decision: str, notes: str = "", quick_tags=None):
    if decision not in VALID_DECISIONS:
        raise ValueError("Invalid decision")
    quick_tags = list(quick_tags or [])
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
        page_state["status"] = "locked"
        page_state["approved_candidate"] = candidate
        page_state["approved_at"] = utc_now()
        page_state["last_decision"] = "approve"

        order = [page["page_id"] for page in tome["pages"]]
        index = order.index(page_id)
        if index + 1 < len(order):
            next_id = order[index + 1]
            state["current_page_id"] = next_id
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
    append_review({
        "page_id": page_id,
        "decision": decision,
        "candidate": candidate,
        "notes": notes.strip(),
        "quick_tags": quick_tags,
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
            self.serve_static(path)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self.read_body_json()
            if path == "/api/decision":
                self.send_json(apply_decision(
                    payload.get("decision", ""),
                    payload.get("notes", ""),
                    payload.get("quick_tags", []),
                ))
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
