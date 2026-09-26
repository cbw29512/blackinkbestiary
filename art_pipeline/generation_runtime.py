from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    from .manifest_validation import validate_manifest
    from .page_contract import resolve_page_spec
    from .png_content_qa import enforce_print_safe_margin, normalize_monochrome_line_art
    from .studio_config import active_book_paths
except ImportError:
    from manifest_validation import validate_manifest
    from page_contract import resolve_page_spec
    from png_content_qa import enforce_print_safe_margin, normalize_monochrome_line_art
    from studio_config import active_book_paths

ROOT = Path(__file__).resolve().parents[1]
_BOOK_PATHS = active_book_paths(ROOT)
TOME_FILE = _BOOK_PATHS["manifest"]
STATE_FILE = _BOOK_PATHS["state"]
MONSTER_DIR = ROOT / "data" / "monsters"
WEB_DIR = ROOT / "web"
CANDIDATE_DIR = WEB_DIR / "candidates"
STUDIO_URL = "http://127.0.0.1:8765"


class TechnicalQAError(RuntimeError):
    """Generated image exists, but failed deterministic production QA."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def current_context():
    tome = read_json(TOME_FILE)
    errors = validate_manifest(ROOT, tome, MONSTER_DIR)
    if errors:
        raise RuntimeError("Production manifest invalid: " + " | ".join(errors))
    state = read_json(STATE_FILE)
    page_id = state["current_page_id"]
    page = next(item for item in tome["pages"] if item["page_id"] == page_id)
    return resolve_page_spec(page, ROOT), state["pages"][page_id]


def set_page_status(page_id: str, status: str, error: str | None = None) -> None:
    state = read_json(STATE_FILE)
    if state["current_page_id"] != page_id:
        return
    entry = state["pages"][page_id]
    entry["status"] = status
    if error:
        entry["generation_error"] = {"message": error, "at": utc_now()}
    else:
        entry.pop("generation_error", None)
    state["updated_at"] = utc_now()
    write_json(STATE_FILE, state)


def model_filename(config: dict, folder: str) -> str:
    match = next((item for item in config["models"] if item.get("folder") == folder), None)
    if not match:
        raise RuntimeError(f"No model configured for {folder}")
    return match["filename"]


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


def post_candidate(payload: dict) -> None:
    request = urllib.request.Request(
        STUDIO_URL + "/api/candidate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def current_source(page_state: dict) -> Path:
    candidate = page_state.get("current_candidate") or {}
    relative = Path(str(candidate.get("image_path") or ""))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("Modify requires a safe current candidate image path")
    source = (WEB_DIR / relative).resolve()
    if WEB_DIR.resolve() not in source.parents or not source.exists():
        raise RuntimeError(f"Modify source image is missing: {relative.as_posix()}")
    return source


def collect_output(client, images: list[dict], page_id: str, attempt: int, inspector) -> str:
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    accepted = None
    reports = []
    for index, image in enumerate(images, 1):
        destination = CANDIDATE_DIR / f"{page_id}-A{attempt:03d}-{index}.png"
        client.download_image(image, destination)
        normalize_monochrome_line_art(destination)
        enforce_print_safe_margin(destination)
        report = inspector(destination)
        reports.append(report)
        if accepted is None and report.get("pass"):
            accepted = destination
    if accepted is None:
        raise TechnicalQAError(
            f"No output passed production QA: {[item.get('reasons') for item in reports]}"
        )
    return accepted.relative_to(WEB_DIR).as_posix()
