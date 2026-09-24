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


def preflight_commands() -> list[tuple[str, list[str]]]:
    return [
        (
            "unit-tests",
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
                "-v",
            ],
        ),
        (
            "active-book-audit",
            [sys.executable, "scripts/audit_active_book.py"],
        ),
        (
            "series-audit",
            [sys.executable, "scripts/audit_series.py"],
        ),
        (
            "python-compile",
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "art_pipeline",
                "scripts",
                "server.py",
            ],
        ),
    ]


def run_check(stage: str, command: list[str]) -> dict:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return {
            "stage": stage,
            "status": "failed",
            "returncode": None,
            "command": command,
            "output_tail": [f"Could not launch {stage}: {exc}"],
        }

    combined = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    lines = combined.splitlines()
    return {
        "stage": stage,
        "status": "passed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "command": command,
        "output_tail": lines[-120:],
    }


def main() -> int:
    started = utc_now()
    checks = []
    for stage, command in preflight_commands():
        print(f"Preflight: {stage}...")
        check = run_check(stage, command)
        checks.append(check)
        if check["status"] != "passed":
            payload = {
                "schema_version": 2,
                "status": "failed",
                "stage": stage,
                "started_at": started,
                "updated_at": utc_now(),
                "python": sys.executable,
                "checks": checks,
                "returncode": check["returncode"],
                "command": check["command"],
                "output_tail": check["output_tail"],
            }
            write_status(payload)
            print(f"Engine preflight failed at {stage}. Diagnostic saved for GitHub publication.")
            for line in check["output_tail"][-40:]:
                print(line)
            return int(check["returncode"] or 1)

    payload = {
        "schema_version": 2,
        "status": "passed",
        "stage": "complete",
        "started_at": started,
        "updated_at": utc_now(),
        "python": sys.executable,
        "checks": checks,
        "returncode": 0,
        "command": None,
        "output_tail": ["All local non-GPU engine checks passed."],
    }
    write_status(payload)
    print("Engine preflight passed: unit tests, active-book audit, series audit, and Python compile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
