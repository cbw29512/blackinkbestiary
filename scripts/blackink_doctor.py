from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "local_ai_stack.json"
REPORT = ROOT / "data" / "local-environment.json"


def get_json(url: str, timeout: float = 3.0):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def command_version(command: str):
    try:
        result = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        text = (result.stdout or result.stderr or "").strip()
        return {"ok": result.returncode == 0, "text": text, "returncode": result.returncode}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def find_comfy():
    candidates = []
    path_hit = shutil.which("comfy")
    if path_hit:
        candidates.append(Path(path_hit))
    local = ROOT / ".blackink-tools" / "Scripts" / "comfy.exe"
    if local.exists():
        candidates.append(local)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def server_probe(base_url: str, required_models: list[dict]):
    result = {"connected": False, "url": base_url}
    try:
        stats = get_json(base_url.rstrip("/") + "/system_stats")
    except Exception as exc:
        result["error"] = str(exc)
        return result

    result["connected"] = True
    result["system"] = stats.get("system", {})
    result["devices"] = stats.get("devices", [])
    result["models"] = {}

    for spec in required_models:
        folder = spec["folder"]
        try:
            names = get_json(base_url.rstrip("/") + "/models/" + urllib.parse.quote(folder))
        except Exception as exc:
            result["models"][folder] = {"error": str(exc), "files": []}
            continue
        result["models"][folder] = {
            "files": names,
            "required": spec["filename"],
            "present": spec["filename"] in names,
        }
    return result


def status_line(label: str, ok: bool, detail: str = ""):
    mark = "OK" if ok else "WAIT"
    suffix = f" — {detail}" if detail else ""
    print(f"[{mark:4}] {label}{suffix}")


def main():
    parser = argparse.ArgumentParser(description="Black-Ink Bestiary local AI doctor")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON")
    args = parser.parse_args()

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    py_ok = sys.version_info >= (3, 10)
    comfy_bin = find_comfy()
    comfy_version = command_version(comfy_bin) if comfy_bin else {"ok": False, "error": "not found"}
    server = server_probe(config["comfy_url"], config["models"])

    missing = []
    if server.get("connected"):
        for spec in config["models"]:
            folder = spec["folder"]
            entry = server.get("models", {}).get(folder, {})
            if not entry.get("present"):
                missing.append(spec["filename"])
    else:
        missing = [spec["filename"] for spec in config["models"]]

    system = server.get("system", {})
    devices = server.get("devices", [])
    primary = devices[0] if devices else {}
    vram_total = primary.get("vram_total")
    vram_gb = round(vram_total / (1024 ** 3), 1) if isinstance(vram_total, (int, float)) else None

    report = {
        "ready_for_model_download": bool(py_ok and comfy_bin),
        "ready_for_generation": bool(py_ok and comfy_bin and server.get("connected") and not missing),
        "python": {
            "ok": py_ok,
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "comfy_cli": {
            "found": bool(comfy_bin),
            "path": comfy_bin,
            "version_result": comfy_version,
            "pinned_version": config["comfy_cli_version"],
        },
        "comfyui": server,
        "gpu": {
            "name": primary.get("name"),
            "vram_gb": vram_gb,
        },
        "required_models_missing": missing,
        "templates": config["templates"],
        "policy": config["production_policy"],
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["ready_for_generation"] else 2

    print()
    print("Black-Ink Bestiary — Local AI Doctor")
    print("====================================")
    status_line("Python 3.10+", py_ok, platform.python_version())
    status_line("Pinned comfy-cli available", bool(comfy_bin), comfy_bin or "project tool not installed yet")
    if comfy_bin:
        status_line("comfy-cli responds", comfy_version.get("ok", False), comfy_version.get("text") or comfy_version.get("error", ""))

    status_line("ComfyUI local server", server.get("connected", False), config["comfy_url"])
    if server.get("connected"):
        status_line("ComfyUI version", True, str(system.get("comfyui_version", "unknown")))
        status_line("PyTorch", True, str(system.get("pytorch_version", "unknown")))
        status_line("GPU", bool(primary), f"{primary.get('name', 'unknown')} / {vram_gb or '?'} GB VRAM")
        argv = system.get("argv") or []
        if argv:
            print("       launch args: " + " ".join(str(x) for x in argv))

    if server.get("connected"):
        for spec in config["models"]:
            entry = server.get("models", {}).get(spec["folder"], {})
            status_line(
                spec["filename"],
                entry.get("present", False),
                f"models/{spec['folder']}",
            )
    else:
        print("[WAIT] Model checks — start ComfyUI first so its active model paths can be queried")

    print()
    if report["ready_for_generation"]:
        print("RESULT: CORE MODEL FILES PRESENT. Ready for official-template validation and I-01 smoke test.")
    elif py_ok and comfy_bin and not server.get("connected"):
        print("RESULT: TOOLING READY. ComfyUI must be installed/opened before the next automatic checks.")
    elif py_ok and comfy_bin and server.get("connected") and missing:
        print("RESULT: COMFYUI READY. Required FLUX model files are missing; downloader can install them next.")
    else:
        print("RESULT: LOCAL TOOL BOOTSTRAP REQUIRED.")

    print(f"Machine report saved to: {REPORT}")
    return 0 if report["ready_for_generation"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
