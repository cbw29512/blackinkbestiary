from __future__ import annotations

import filecmp
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .manifest_validation import validate_manifest
from .studio_config import active_book_paths
from .state_validation import assert_valid_state

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"
MONSTER_DIR = DATA_DIR / "monsters"
APPROVED_ROOT = WEB_DIR / "approved"

_BOOK_PATHS = active_book_paths(ROOT)
TOME_FILE = _BOOK_PATHS["manifest"]
STATE_FILE = _BOOK_PATHS["state"]
REVIEWS_FILE = _BOOK_PATHS["reviews"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_tome():
    tome = read_json(TOME_FILE)
    errors = validate_manifest(ROOT, tome, MONSTER_DIR)
    if errors:
        raise ValueError("Production manifest invalid: " + " | ".join(errors))
    return tome


def load_state():
    return read_json(STATE_FILE)


def validate_state(tome, state) -> None:
    assert_valid_state(tome, state)


def page_by_id(tome, page_id: str):
    return next((page for page in tome["pages"] if page["page_id"] == page_id), None)


def load_monster_spec(page: dict):
    spec_id = str(page.get("monster_spec_id", "")).strip()
    if not spec_id:
        return None
    path = MONSTER_DIR / f"{spec_id}.json"
    if not path.exists():
        raise ValueError(f"Monster spec not found: {spec_id}")
    spec = read_json(path)
    if spec.get("monster_id") != spec_id:
        raise ValueError(f"Monster spec ID mismatch: {spec_id}")
    return spec


def public_monster_spec(page: dict):
    spec = load_monster_spec(page)
    if not spec:
        return None
    payload = json.loads(json.dumps(spec))
    reference = payload.get("reference") or {}
    image = str(reference.get("image") or "").strip()
    resolved = None
    if image:
        relative = Path(image)
        if not relative.is_absolute() and ".." not in relative.parts:
            target = (WEB_DIR / relative).resolve()
            web_root = WEB_DIR.resolve()
            if target.exists() and target.is_file() and (
                target == web_root or web_root in target.parents
            ):
                resolved = relative.as_posix()
    reference["resolved_image"] = resolved
    payload["reference"] = reference
    return payload


def append_review(entry: dict) -> None:
    REVIEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REVIEWS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def tome_folder_name(tome: dict) -> str:
    tome_id = str(tome.get("tome_id", "TOME-I")).strip()
    if tome_id.upper().startswith("TOME-"):
        return "Tome-" + tome_id.split("-", 1)[1]
    return tome_id or "Tome-I"


def archive_approved_candidate(tome: dict, page_id: str, candidate: dict) -> str:
    image_path = str(candidate.get("image_path", "")).strip()
    if not image_path:
        raise ValueError("Candidate has no image_path")

    relative = Path(image_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Candidate image_path must stay inside the Studio web folder")

    source = (WEB_DIR / relative).resolve()
    web_root = WEB_DIR.resolve()
    if source != web_root and web_root not in source.parents:
        raise ValueError("Candidate image is outside the Studio web folder")
    if not source.exists() or not source.is_file():
        raise ValueError(f"Candidate image file does not exist: {image_path}")
    if source.suffix.lower() != ".png":
        raise ValueError("Approved production pages must be PNG files")

    destination = APPROVED_ROOT / tome_folder_name(tome) / f"{page_id}.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not filecmp.cmp(source, destination, shallow=False):
        raise ValueError(
            "Approved page already exists with different artwork: "
            + destination.relative_to(WEB_DIR).as_posix()
        )
    if not destination.exists():
        shutil.copy2(source, destination)
    return destination.relative_to(WEB_DIR).as_posix()
