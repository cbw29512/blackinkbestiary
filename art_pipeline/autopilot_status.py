from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CANARY_CONFIG = ROOT / "config" / "quality_scorecard.json"
STALE_AFTER_SECONDS = 20 * 60


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _canary_ids() -> list[str]:
    payload = _read_json(CANARY_CONFIG, {})
    return [str(x) for x in payload.get("canary_page_ids") or [] if str(x)]


def _parse_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def activity_health(
    heartbeat: dict,
    progress: dict,
    gallery: dict,
    runtime: dict,
    preflight: dict,
    engine_commit: str,
    *,
    now: datetime | None = None,
) -> dict:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    sources = {
        "heartbeat": heartbeat.get("updated_at"),
        "generation_progress": progress.get("updated_at"),
        "gallery": gallery.get("updated_at"),
        "runtime": runtime.get("updated_at"),
        "preflight": preflight.get("updated_at"),
    }
    parsed = [(name, _parse_time(value)) for name, value in sources.items()]
    parsed = [(name, value) for name, value in parsed if value is not None]
    freshest_source, freshest_at = max(parsed, key=lambda pair: pair[1]) if parsed else (None, None)
    age_seconds = None if freshest_at is None else max(0, int((now - freshest_at).total_seconds()))
    stale = age_seconds is None or age_seconds > STALE_AFTER_SECONDS
    heartbeat_engine = str(heartbeat.get("engine_commit") or "")
    return {
        "status": "stale" if stale else str(heartbeat.get("status") or "unknown"),
        "stale": stale,
        "stale_after_seconds": STALE_AFTER_SECONDS,
        "last_activity_at": freshest_at.isoformat() if freshest_at else None,
        "last_activity_source": freshest_source,
        "age_seconds": age_seconds,
        "engine_current": bool(heartbeat_engine and heartbeat_engine == engine_commit),
        "heartbeat_engine_commit": heartbeat_engine or None,
    }


def public_autopilot_status() -> dict:
    heartbeat = _read_json(DATA / "autopilot-heartbeat.json", {})
    gallery = _read_json(DATA / "test-gallery-state.json", {"results": []})
    runtime = _read_json(DATA / "local-runtime-status.json", {})
    preflight = _read_json(DATA / "engine-preflight-status.json", {})
    quality = _read_json(ROOT / "review-previews" / "quality-current.json", {})
    progress = _read_json(DATA / "generation-progress.json", {})
    engine_commit = _git_head()
    worker_health = activity_health(
        heartbeat,
        progress,
        gallery,
        runtime,
        preflight,
        engine_commit,
    )
    latest_by_page, active, failures = {}, None, []
    for item in gallery.get("results") or []:
        page_id = str(item.get("page_id") or "")
        if page_id:
            latest_by_page[page_id] = item
        if item.get("started_at") and not item.get("finished_at"):
            active = item
        if str(item.get("status") or "") in {"failed", "technical_qa_failed", "vision_reviewer_failed"}:
            failures.append(item)

    rows = []
    counts = {"approved": 0, "review": 0, "failed": 0, "other": 0}
    for page_id in _canary_ids():
        item = latest_by_page.get(page_id) or {}
        status = str(item.get("status") or "missing")
        decision = str((item.get("assistant_review") or {}).get("decision") or "").lower()
        if decision in {"approve", "select"}:
            bucket = "approved"
        elif status in {"awaiting_exact_image_review", "ready_for_review"}:
            bucket = "review"
        elif status in {"failed", "technical_qa_failed", "vision_reviewer_failed"}:
            bucket = "failed"
        else:
            bucket = "other"
        counts[bucket] += 1
        rows.append({
            "page_id": page_id, "monster_name": item.get("monster_name"),
            "status": status, "bucket": bucket, "engine_commit": item.get("engine_commit"),
            "started_at": item.get("started_at"), "finished_at": item.get("finished_at"),
            "image_path": item.get("image_path"), "error": item.get("error"),
            "review_stage": (item.get("visual_review") or {}).get("stage"),
            "review_score": (item.get("visual_review") or {}).get("score"),
        })
    return {
        "engine_commit": engine_commit, "heartbeat": heartbeat, "worker_health": worker_health,
        "runtime": runtime,
        "preflight": preflight, "quality": quality, "active_candidate": active,
        "generation_progress": progress,
        "canary_counts": counts, "canary_total": len(rows), "canaries": rows,
        "latest_failures": [{
            "page_id": item.get("page_id"), "status": item.get("status"),
            "error": item.get("error"), "finished_at": item.get("finished_at"),
        } for item in failures[-5:]],
        "gallery_updated_at": gallery.get("updated_at"),
    }
