from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "engine-preflight-status.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_status(payload: dict) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    started = utc_now()
    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_*.py",
        "-v",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    combined = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    lines = combined.splitlines()
    tail = lines[-120:]

    payload = {
        "schema_version": 1,
        "status": "passed" if result.returncode == 0 else "failed",
        "stage": "unit-tests",
        "started_at": started,
        "updated_at": utc_now(),
        "returncode": result.returncode,
        "python": sys.executable,
        "command": command,
        "output_tail": tail,
    }
    write_status(payload)

    if result.returncode == 0:
        print("Engine preflight passed.")
        return 0

    print("Engine preflight failed. Diagnostic saved for GitHub publication.")
    for line in tail[-40:]:
        print(line)
    return result.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
