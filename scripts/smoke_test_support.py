from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from page_contract import resolve_page_spec

LOGGER = logging.getLogger(__name__)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not read smoke-test JSON: %s", path)
        raise RuntimeError(f"Could not read smoke-test JSON {path}: {exc}") from exc


def load_current(root: Path = ROOT) -> tuple[dict, dict]:
    tome = read_json(root / "data" / "tome-I.json")
    state = read_json(root / "data" / "production-state.json")
    page_id = str(state.get("current_page_id") or "").strip()
    raw_page = next(
        (page for page in tome.get("pages", []) if page.get("page_id") == page_id),
        None,
    )
    if not raw_page:
        raise RuntimeError(f"Current smoke-test page is missing from manifest: {page_id}")
    page_state = (state.get("pages") or {}).get(page_id)
    if not isinstance(page_state, dict):
        raise RuntimeError(f"Current smoke-test page is missing from state: {page_id}")
    return resolve_page_spec(raw_page, root), page_state


def find_prompt_id(value):
    if isinstance(value, dict):
        if isinstance(value.get("prompt_id"), str):
            return value["prompt_id"]
        for child in value.values():
            found = find_prompt_id(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_prompt_id(child)
            if found:
                return found
    return None


def model_filename(config: dict, folder: str) -> str:
    match = next(
        (model for model in config.get("models", []) if model.get("folder") == folder),
        None,
    )
    if not match or not str(match.get("filename") or "").strip():
        raise RuntimeError(f"No model configured for {folder}")
    return str(match["filename"])


def studio_health(studio_url: str) -> bool:
    try:
        with urllib.request.urlopen(studio_url + "/api/health", timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False


def ensure_studio(root: Path, studio_url: str) -> None:
    if studio_health(studio_url):
        return
    kwargs = {
        "cwd": root,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    try:
        subprocess.Popen(
            [sys.executable, str(root / "server.py"), "--no-browser"],
            **kwargs,
        )
    except OSError as exc:
        LOGGER.exception("Could not start local Studio")
        raise RuntimeError(f"Could not start local Studio: {exc}") from exc

    for _ in range(40):
        if studio_health(studio_url):
            return
        time.sleep(0.25)
    raise RuntimeError(f"Studio did not start on {studio_url}")


def post_json(url: str, payload: dict):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        LOGGER.exception("Smoke-test POST failed: %s", url)
        raise RuntimeError(f"Smoke-test POST failed for {url}: {exc}") from exc
