from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "local_ai_stack.json"
MARKER = ROOT / "data" / "local-ai-install-marker.json"


def _config(root: Path) -> dict:
    return json.loads((root / "config" / "local_ai_stack.json").read_text(encoding="utf-8"))


def _config_hash(root: Path) -> str:
    return hashlib.sha256((root / "config" / "local_ai_stack.json").read_bytes()).hexdigest()


def _comfy_root(root: Path) -> Path:
    config = _config(root)
    workspace = root / str(config["workspace"])
    if (workspace / "main.py").is_file():
        return workspace
    nested = workspace / "ComfyUI"
    if (nested / "main.py").is_file():
        return nested
    return workspace


def required_files(root: Path) -> list[Path]:
    config = _config(root)
    comfy_root = _comfy_root(root)
    files = [
        root / ".blackink-tools" / "Scripts" / "python.exe",
        root / ".blackink-tools" / "Scripts" / "comfy.exe",
        comfy_root / "main.py",
    ]
    for model in config.get("models") or []:
        files.append(
            comfy_root
            / "models"
            / str(model["folder"])
            / str(model["filename"])
        )
    return files


def build_marker(root: Path = ROOT) -> dict:
    rows = []
    missing = []
    for path in required_files(root):
        if not path.is_file():
            missing.append(str(path.relative_to(root)).replace("\\", "/"))
            continue
        stat = path.stat()
        rows.append(
            {
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "size_bytes": int(stat.st_size),
            }
        )
    if missing:
        raise RuntimeError(
            "Local AI stack is incomplete; missing: " + ", ".join(missing)
        )
    return {
        "schema_version": 1,
        "config_sha256": _config_hash(root),
        "files": rows,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


def verify_marker(root: Path = ROOT, marker_path: Path | None = None) -> tuple[bool, str]:
    marker_path = marker_path or (root / "data" / "local-ai-install-marker.json")
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, "install marker is missing"
    except json.JSONDecodeError:
        return False, "install marker is invalid JSON"

    if marker.get("schema_version") != 1:
        return False, "install marker schema is unsupported"
    if marker.get("config_sha256") != _config_hash(root):
        return False, "pinned local AI stack configuration changed"

    expected = {
        str(row.get("path") or ""): int(row.get("size_bytes") or -1)
        for row in marker.get("files") or []
    }
    required = [str(path.relative_to(root)).replace("\\", "/") for path in required_files(root)]
    if set(expected) != set(required):
        return False, "install marker does not cover the complete required local stack"

    for relative in required:
        path = root / relative
        if not path.is_file():
            return False, f"required local file is missing: {relative}"
        if path.stat().st_size != expected[relative]:
            return False, f"required local file size changed: {relative}"

    return True, "local AI stack matches the verified install marker"


def write_marker(root: Path = ROOT, marker_path: Path | None = None) -> dict:
    marker_path = marker_path or (root / "data" / "local-ai-install-marker.json")
    payload = build_marker(root)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the installed Black Ink local AI stack.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()

    try:
        if args.write:
            payload = write_marker()
            print(
                f"Local AI install marker written for {len(payload['files'])} required files."
            )
            return 0
        ok, reason = verify_marker()
        print(reason)
        return 0 if ok else 2
    except Exception as exc:
        print(f"Local AI install marker failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
