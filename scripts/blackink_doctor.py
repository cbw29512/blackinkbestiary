from __future__ import annotations

import argparse
import json
import logging
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from local_preflight import local_generation_preflight

CONFIG = ROOT / "config" / "local_ai_stack.json"
REPORT = ROOT / "data" / "local-environment.json"
LOGGER = logging.getLogger("blackink-doctor")


def _read_config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load local AI configuration")
        raise RuntimeError(f"Could not load local AI configuration: {exc}") from exc


def command_version(command: str | None) -> dict:
    if not command:
        return {"ok": False, "error": "not found"}
    try:
        result = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        output = (result.stdout or result.stderr or "").strip()
        return {
            "ok": result.returncode == 0,
            "text": output,
            "returncode": result.returncode,
        }
    except (OSError, subprocess.SubprocessError) as exc:
        LOGGER.info("Could not query comfy-cli version: %s", exc)
        return {"ok": False, "error": str(exc)}


def status_line(label: str, ok: bool, detail: str = "") -> None:
    mark = "OK" if ok else "WAIT"
    suffix = f" — {detail}" if detail else ""
    print(f"[{mark:4}] {label}{suffix}")


def enriched_report() -> dict:
    config = _read_config()
    report = local_generation_preflight(ROOT)
    cli_version = command_version(report.get("comfy_cli_path"))
    report["ready_for_model_download"] = bool(
        report["checks"]["python"] and report["checks"]["comfy_cli"]
    )
    report["comfy_cli"] = {
        "found": report["checks"]["comfy_cli"],
        "path": report.get("comfy_cli_path"),
        "version_result": cli_version,
        "pinned_version": config.get("comfy_cli_version"),
    }
    report["policy"] = config.get("production_policy") or {}
    report["workspace"] = config.get("workspace")
    return report


def print_report(report: dict) -> None:
    print()
    print("Black-Ink Bestiary — Local AI Doctor")
    print("====================================")
    status_line("Python 3.10+", report["checks"]["python"], platform.python_version())
    cli = report["comfy_cli"]
    status_line("Pinned comfy-cli available", cli["found"], cli.get("path") or "not installed")
    status_line(
        "comfy-cli responds",
        cli["version_result"].get("ok", False),
        cli["version_result"].get("text") or cli["version_result"].get("error", ""),
    )
    status_line("ComfyUI local server", report["checks"]["comfyui_server"], report["comfy_url"])
    if report["checks"]["comfyui_server"]:
        status_line("ComfyUI version", True, str(report.get("comfyui_version") or "unknown"))
        device = (report.get("devices") or [{}])[0]
        status_line("GPU", bool(device), str(device.get("name") or "unknown"))

    for model in report.get("models") or []:
        status_line(
            model["filename"],
            model["present"],
            f"models/{model['folder']}",
        )
    status_line("Official templates configured", report["checks"]["templates_configured"])
    status_line("Golden Five generator present", report["checks"]["golden_generator"])
    status_line("Workflow directory present", report["checks"]["workflow_directory"])

    print()
    if report["ready_for_generation"]:
        print("RESULT: LOCAL ARTIST IS GENERATION-READY.")
    elif report["checks"]["comfyui_server"] and report["required_models_missing"]:
        print("RESULT: COMFYUI IS RUNNING, BUT REQUIRED MODEL FILES ARE MISSING.")
    elif not report["checks"]["comfyui_server"]:
        print("RESULT: LOCAL TOOLING MAY BE PRESENT, BUT COMFYUI IS NOT REACHABLE.")
    else:
        print("RESULT: LOCAL GENERATION PREFLIGHT FAILED. Review the WAIT items above.")
    print(f"Machine report saved to: {REPORT}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Black-Ink Bestiary local AI doctor")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        report = enriched_report()
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_report(report)
        return 0 if report["ready_for_generation"] else 2
    except Exception as exc:
        LOGGER.exception("Black-Ink local doctor failed")
        print(f"DOCTOR FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
