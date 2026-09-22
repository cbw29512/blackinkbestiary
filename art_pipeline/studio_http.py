from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import unquote, urlparse

from .studio_candidates import register_candidate
from .studio_production import VALID_DECISIONS, apply_decision, public_state
from .studio_store import WEB_DIR, utc_now
from .studio_worker import (
    GENERATABLE_STATES,
    comfy_health,
    generation_worker_status,
    start_generation_worker,
)


class Handler(BaseHTTPRequestHandler):
    server_version = "BlackInkBestiary/0.2"

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
            elif path == "/api/state":
                self.send_json(public_state())
            elif path == "/api/comfy-health":
                self.send_json(comfy_health())
            elif path == "/api/generation-status":
                self.send_json(generation_worker_status())
            else:
                self.serve_static(path)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self.read_body_json()
            if path == "/api/decision":
                self.handle_decision(payload)
            elif path == "/api/generate":
                self.handle_generate()
            elif path == "/api/candidate":
                self.send_json(register_candidate(payload))
            else:
                self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_decision(self, payload: dict) -> None:
        decision = payload.get("decision", "")
        result = apply_decision(
            decision,
            payload.get("notes", ""),
            payload.get("quick_tags", []),
        )
        if (
            decision in VALID_DECISIONS
            and result["current_state"]["status"] in GENERATABLE_STATES
        ):
            result["generation_worker"] = start_generation_worker()
        self.send_json(result)

    def handle_generate(self) -> None:
        worker = start_generation_worker()
        result = public_state()
        result["generation_worker"] = worker
        self.send_json(result)

    def serve_static(self, request_path: str) -> None:
        rel = unquote(request_path.lstrip("/")) or "index.html"
        target = (WEB_DIR / rel).resolve()
        web_root = WEB_DIR.resolve()
        if web_root not in target.parents and target != web_root:
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
