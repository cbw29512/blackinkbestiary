from __future__ import annotations

import argparse
import json
import mimetypes
import subprocess
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
TEST_GALLERY_STATE = ROOT / "data" / "test-gallery-state.json"
QUALITY_CURRENT = ROOT / "review-previews" / "quality-current.json"
REVIEW_DECISIONS = ROOT / "review-previews" / "decisions.json"
QUALITY_SCORECARD = ROOT / "config" / "quality_scorecard.json"

sys.path.insert(0, str(ROOT / "art_pipeline"))

from human_review import (
    REVIEWABLE_STATUSES,
    append_human_decision,
    configured_canary_ids,
    current_image_path,
    exact_review_id,
)
from learning_feedback import human_feedback_summary
from page_contract import resolve_page_spec
from review_authority import decision_is_authoritative
from studio_config import active_book_paths

LOCAL_ONLY_HOSTS = {"127.0.0.1", "localhost", "::1"}


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


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


def load_page_contexts() -> dict[str, dict]:
    paths = active_book_paths(ROOT)
    manifest = read_json(paths["manifest"], {"pages": []})
    result = {}
    for raw in manifest.get("pages", []):
        page_id = str(raw.get("page_id") or "")
        if not page_id:
            continue
        try:
            result[page_id] = resolve_page_spec(raw, ROOT)
        except Exception:
            # Fall back to raw page data so the review server remains usable
            # even if non-review authority is temporarily broken.
            result[page_id] = raw
    return result


def safe_image_url(item: dict) -> str | None:
    try:
        path = current_image_path(ROOT, item).resolve()
        web_root = WEB_DIR.resolve()
    except OSError:
        return None
    if not path.exists() or not path.is_file():
        return None
    if path != web_root and web_root not in path.parents:
        return None
    return "/" + path.relative_to(web_root).as_posix()


def human_history() -> dict[str, list[dict]]:
    payload = read_json(REVIEW_DECISIONS, {"reviews": []})
    result: dict[str, list[dict]] = {}
    for row in payload.get("reviews", []):
        if str(row.get("reviewer") or "").strip().lower() != "human":
            continue
        page_id = str(row.get("page_id") or "").strip()
        if not page_id:
            continue
        result.setdefault(page_id, []).append({
            "decision": row.get("decision"),
            "stage": row.get("stage"),
            "notes": row.get("notes"),
            "decided_at": row.get("decided_at"),
            "review_id": row.get("review_id"),
        })
    return result


def latest_canary_records() -> dict[str, dict]:
    state = read_json(TEST_GALLERY_STATE, {"results": []})
    canary_ids = set(configured_canary_ids(ROOT))
    latest: dict[str, dict] = {}
    for item in state.get("results", []):
        page_id = str(item.get("page_id") or "")
        if page_id not in canary_ids:
            continue
        if int(item.get("candidate") or 0) != 1:
            continue
        latest[page_id] = item
    return latest


def public_review_state() -> dict:
    canary_ids = configured_canary_ids(ROOT)
    latest = latest_canary_records()
    contexts = load_page_contexts()
    history = human_history()
    pages = []

    for page_id in canary_ids:
        item = latest.get(page_id) or {}
        page = contexts.get(page_id) or {}
        status = str(item.get("status") or "missing")
        assistant = item.get("assistant_review") or {}
        review_id = None
        if item:
            try:
                review_id = exact_review_id(ROOT, item)
            except ValueError:
                review_id = None

        authoritative = bool(item) and decision_is_authoritative(assistant, ROOT)
        decision = str(assistant.get("decision") or "").strip().lower()
        human_approved = bool(
            authoritative
            and decision in {"approve", "select"}
            and review_id
            and str(assistant.get("review_id") or "").strip() == review_id
        )
        awaiting_human = bool(
            item
            and status in REVIEWABLE_STATUSES
            and review_id
            and not human_approved
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
            "image_url": safe_image_url(item) if item else None,
            "human_approved": human_approved,
            "awaiting_human": awaiting_human,
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

    scorecard = read_json(QUALITY_SCORECARD, {})
    quality = read_json(QUALITY_CURRENT, {})
    engine = current_engine_commit()
    expected_contract = str(scorecard.get("contract_version") or "")
    measured_contract = str(quality.get("quality_contract_version") or "")
    measured_engine = str(quality.get("engine_commit") or "")
    stale = bool(
        not quality
        or measured_contract != expected_contract
        or (engine != "unknown" and measured_engine and measured_engine != engine)
    )

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
            "measured_engine_commit": measured_engine or None,
            "measured_contract_version": measured_contract or None,
            "stale": stale,
        },
        "human_feedback": human_feedback_summary(ROOT),
        "pages": pages,
    }


def apply_web_decision(payload: dict) -> dict:
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

    match = latest_canary_records().get(page_id)
    if not match or int(match.get("candidate") or 0) != candidate:
        raise ValueError("Current Canary candidate was not found.")
    if str(match.get("status") or "") not in REVIEWABLE_STATUSES:
        raise ValueError("This Canary is no longer awaiting human review.")

    current_id = exact_review_id(ROOT, match)
    if supplied_review_id != current_id:
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
        [sys.executable, str(ROOT / "scripts" / "apply_review_decisions.py")],
        cwd=ROOT,
        check=True,
    )
    publish = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "publish_review_previews.py")],
        cwd=ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    result = public_review_state()
    result["saved_decision"] = row
    result["published"] = publish.returncode == 0
    if publish.returncode != 0:
        detail = (publish.stderr or publish.stdout or "").strip().splitlines()
        result["publish_warning"] = (
            detail[-1]
            if detail
            else "Review snapshot publish failed; the local decision is still saved."
        )
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "BlackInkReview/1.0"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}", flush=True)

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("Request too large")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/health":
                self.send_json({
                    "ok": True,
                    "service": "human-review",
                    "engine_commit": current_engine_commit(),
                })
                return
            if path == "/api/human-review":
                self.send_json(public_review_state())
                return
            self.serve_static(path)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path != "/api/human-review/decision":
                self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(apply_web_decision(self.read_json_body()))
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except subprocess.CalledProcessError as exc:
            self.send_json(
                {"error": f"Decision was saved, but applying it failed with exit code {exc.returncode}."},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def serve_static(self, request_path: str):
        rel = unquote(request_path.lstrip("/")) or "human-review.html"
        target = (WEB_DIR / rel).resolve()
        web_root = WEB_DIR.resolve()
        if target != web_root and web_root not in target.parents:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if target.is_dir():
            target = target / "human-review.html"
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


def run(host: str = "127.0.0.1", port: int = 8766):
    if str(host or "").strip().lower() not in LOCAL_ONLY_HOSTS:
        raise ValueError("Human Review Studio is local-only.")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Black Ink Bestiary Human Review Studio: http://{host}:{port}/human-review.html", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Black Ink Bestiary local-only Human Review Studio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    run(args.host, args.port)
