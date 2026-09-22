from __future__ import annotations

import json
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

from .studio_store import DATA_DIR, ROOT, load_state, load_tome, page_by_id

GENERATOR_SCRIPT = ROOT / "scripts" / "generate_current_page.py"
GENERATOR_LOG = DATA_DIR / "generation-worker.log"
GENERATABLE_STATES = {
    "queued",
    "modify_requested",
    "regenerate_requested",
    "generation_failed",
}

_GENERATION_LOCK = threading.Lock()
_GENERATION_PROCESS = None


def comfy_health() -> dict:
    url = "http://127.0.0.1:8188/system_stats"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        devices = [
            {
                "name": item.get("name"),
                "type": item.get("type"),
                "vram_total": item.get("vram_total"),
                "vram_free": item.get("vram_free"),
            }
            for item in payload.get("devices", [])
        ]
        return {"connected": True, "url": "http://127.0.0.1:8188", "devices": devices}
    except Exception as exc:
        return {
            "connected": False,
            "url": "http://127.0.0.1:8188",
            "error": str(exc),
        }


def worker_python() -> str:
    local = ROOT / ".blackink-tools" / "Scripts" / "python.exe"
    return str(local) if local.exists() else sys.executable


def generation_worker_status() -> dict:
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


def start_generation_worker() -> dict:
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
            return {
                "started": False,
                "running": True,
                "pid": _GENERATION_PROCESS.pid,
            }

        GENERATOR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with GENERATOR_LOG.open("a", encoding="utf-8") as log:
            creationflags = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if sys.platform == "win32"
                else 0
            )
            process = subprocess.Popen(
                [worker_python(), str(GENERATOR_SCRIPT)],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
        _GENERATION_PROCESS = process
        return {
            "started": True,
            "running": True,
            "pid": process.pid,
            "page_id": page_id,
        }
