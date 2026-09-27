from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "autopilot-heartbeat.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def engine_commit(root: Path = ROOT) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def write_heartbeat(
    phase: str,
    status: str = "running",
    message: str = "",
    *,
    path: Path = STATUS,
    root: Path = ROOT,
) -> dict:
    payload = {
        "schema_version": 1,
        "source": "RUN_ENGINE_AUTOPILOT.bat",
        "phase": str(phase or "unknown"),
        "status": str(status or "unknown"),
        "message": str(message or ""),
        "engine_commit": engine_commit(root),
        "updated_at": utc_now(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase")
    parser.add_argument("status", nargs="?", default="running")
    parser.add_argument("message", nargs="?", default="")
    args = parser.parse_args()
    payload = write_heartbeat(args.phase, args.status, args.message)
    print(
        f"Autopilot heartbeat: {payload['phase']} / {payload['status']} "
        f"@ {payload['engine_commit'][:8]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
