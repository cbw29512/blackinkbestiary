from __future__ import annotations

import json
import logging
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from .comfy_cli_runner import find_comfy_cli
except ImportError:
    from comfy_cli_runner import find_comfy_cli

LOGGER = logging.getLogger(__name__)


def _get_json(url: str, timeout: float = 1.5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        LOGGER.info("Local preflight probe failed for %s: %s", url, exc)
        return None


def _config(root: Path) -> dict:
    path = root / "config" / "local_ai_stack.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load local AI config")
        raise RuntimeError(f"Could not load local AI config: {exc}") from exc


def local_generation_preflight(root: Path) -> dict:
    config = _config(root)
    base_url = str(config.get("comfy_url") or "http://127.0.0.1:8188").rstrip("/")
    python_ok = sys.version_info >= (3, 10)
    cli_path = find_comfy_cli()
    cli_ok = bool(cli_path)

    stats = _get_json(base_url + "/system_stats")
    server_ok = isinstance(stats, dict)
    devices = list((stats or {}).get("devices") or [])
    system = dict((stats or {}).get("system") or {})

    model_checks = []
    missing_models = []
    for spec in config.get("models") or []:
        folder = str(spec.get("folder") or "").strip()
        filename = str(spec.get("filename") or "").strip()
        names = (
            _get_json(base_url + "/models/" + urllib.parse.quote(folder))
            if server_ok and folder
            else None
        )
        present = isinstance(names, list) and filename in names
        if not present:
            missing_models.append(filename)
        model_checks.append({
            "folder": folder,
            "filename": filename,
            "present": present,
            "query_ok": isinstance(names, list),
        })

    templates = config.get("templates") or {}
    templates_configured = bool(
        str(templates.get("text_to_image") or "").strip()
        and str(templates.get("modify") or "").strip()
    )
    generator_present = (root / "scripts" / "generate_golden_page.py").is_file()
    workflow_parent_present = (root / "art_pipeline" / "workflows").is_dir()

    checks = {
        "python": python_ok,
        "comfy_cli": cli_ok,
        "comfyui_server": server_ok,
        "required_models": not missing_models,
        "templates_configured": templates_configured,
        "golden_generator": generator_present,
        "workflow_directory": workflow_parent_present,
    }
    ready = all(checks.values())

    return {
        "ready_for_generation": ready,
        "checks": checks,
        "python_version": ".".join(str(item) for item in sys.version_info[:3]),
        "comfy_cli_path": cli_path,
        "comfy_url": base_url,
        "comfyui_version": system.get("comfyui_version"),
        "devices": devices,
        "models": model_checks,
        "required_models_missing": missing_models,
        "templates": templates,
    }
