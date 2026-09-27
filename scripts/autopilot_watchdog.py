from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "autopilot-watchdog-status.json"

SOURCES = {
    "heartbeat": Path("data/autopilot-heartbeat.json"),
    "generation_progress": Path("data/generation-progress.json"),
    "gallery": Path("data/test-gallery-state.json"),
    "runtime": Path("data/local-runtime-status.json"),
    "preflight": Path("data/engine-preflight-status.json"),
}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


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


def build_health(
    root: Path = ROOT,
    *,
    max_age_minutes: int = 45,
    now: datetime | None = None,
) -> dict:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    source_times = {}
    freshest_source = None
    freshest_at = None

    for name, relative in SOURCES.items():
        payload = _read_json(root / relative)
        raw = payload.get("updated_at")
        source_times[name] = str(raw) if raw else None
        parsed = _parse_time(raw)
        if parsed is not None and (freshest_at is None or parsed > freshest_at):
            freshest_at = parsed
            freshest_source = name

    age_seconds = (
        None
        if freshest_at is None
        else max(0, int((now - freshest_at).total_seconds()))
    )
    stale_after_seconds = max(1, int(max_age_minutes)) * 60
    stale = age_seconds is None or age_seconds > stale_after_seconds

    return {
        "schema_version": 1,
        "status": "stale" if stale else "healthy",
        "stale": stale,
        "max_age_minutes": int(max_age_minutes),
        "stale_after_seconds": stale_after_seconds,
        "last_activity_at": freshest_at.isoformat() if freshest_at else None,
        "last_activity_source": freshest_source,
        "age_seconds": age_seconds,
        "sources": source_times,
        "checked_at": now.isoformat(),
    }


def write_status(report: dict, path: Path = STATUS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed health check for the local Bestiary autopilot."
    )
    parser.add_argument("--max-age-minutes", type=int, default=45)
    args = parser.parse_args()
    report = build_health(max_age_minutes=args.max_age_minutes)
    write_status(report)
    print(json.dumps(report, indent=2))
    return 10 if report["stale"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
