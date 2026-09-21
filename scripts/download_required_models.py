from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "local_ai_stack.json"


def get_json(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def comfy_root_from_stats(stats: dict) -> Path:
    system = stats.get("system") or {}
    argv = [str(x) for x in (system.get("argv") or [])]
    if not argv:
        raise RuntimeError("ComfyUI did not report its launch argv; cannot determine its model directory safely.")

    main = Path(argv[0]).expanduser()
    if not main.is_absolute():
        raise RuntimeError(f"ComfyUI main path is not absolute: {main}")
    root = main.parent
    if not (root / "main.py").exists() and main.name.lower() != "main.py":
        raise RuntimeError(f"Could not verify ComfyUI root from argv[0]: {main}")
    return root


def models_root_from_stats(stats: dict, comfy_root: Path) -> Path:
    argv = [str(x) for x in ((stats.get("system") or {}).get("argv") or [])]
    for index, arg in enumerate(argv):
        if arg == "--models-directory" and index + 1 < len(argv):
            return Path(argv[index + 1]).expanduser().resolve()
        if arg.startswith("--models-directory="):
            return Path(arg.split("=", 1)[1]).expanduser().resolve()
    return (comfy_root / "models").resolve()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_resumable(url: str, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    existing = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": "Black-Ink-Bestiary/1.0"}
    if existing:
        headers["Range"] = f"bytes={existing}-"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        status = getattr(response, "status", 200)
        if existing and status != 206:
            existing = 0
            partial.unlink(missing_ok=True)
        mode = "ab" if existing and status == 206 else "wb"
        total_header = response.headers.get("Content-Length")
        incoming = int(total_header) if total_header and total_header.isdigit() else None
        total = existing + incoming if incoming is not None else None

        with partial.open(mode) as out:
            downloaded = existing
            while True:
                chunk = response.read(8 * 1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 / total
                    print(f"  {destination.name}: {pct:5.1f}% ({downloaded / 1e9:.2f} GB)", end="\r", flush=True)
                else:
                    print(f"  {destination.name}: {downloaded / 1e9:.2f} GB", end="\r", flush=True)
    print()
    return partial


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    base = config["comfy_url"].rstrip("/")
    try:
        stats = get_json(base + "/system_stats")
    except Exception as exc:
        print(f"ComfyUI is not reachable at {base}. Open it first.\n{exc}")
        return 2

    comfy_root = comfy_root_from_stats(stats)
    models_root = models_root_from_stats(stats, comfy_root)
    models_root.mkdir(parents=True, exist_ok=True)

    required = sum(int(item.get("size_bytes") or 0) for item in config["models"])
    free = shutil.disk_usage(models_root).free
    print(f"ComfyUI: {comfy_root}")
    print(f"Models:  {models_root}")
    print(f"Required model payload: about {required / 1e9:.1f} GB")
    print(f"Free disk space:         about {free / 1e9:.1f} GB")
    if free < required + 2_000_000_000:
        print("Not enough free disk space for a safe download margin.")
        return 3

    for spec in config["models"]:
        destination = models_root / spec["folder"] / spec["filename"]
        expected = spec["sha256"].lower()

        if destination.exists():
            print(f"Checking existing {spec['filename']}...")
            actual = sha256(destination).lower()
            if actual == expected:
                print("  OK — existing file hash matches.")
                continue
            print(f"  Existing file hash mismatch. Refusing to overwrite: {destination}")
            print(f"  expected {expected}")
            print(f"  actual   {actual}")
            return 4

        print(f"Downloading {spec['filename']}...")
        partial = download_resumable(spec["url"], destination)
        print("  Verifying SHA256...")
        actual = sha256(partial).lower()
        if actual != expected:
            print("  HASH MISMATCH — partial file kept for diagnosis; final filename was not created.")
            print(f"  expected {expected}")
            print(f"  actual   {actual}")
            return 5
        os.replace(partial, destination)
        print(f"  OK — {destination}")

    print("\nAll required Black-Ink model files are installed and hash-verified.")
    print("Restart ComfyUI so it refreshes its model lists, then run VALIDATE_LOCAL_TEMPLATES.bat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
