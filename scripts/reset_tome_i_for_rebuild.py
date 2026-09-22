from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOME_FILE = ROOT / "data" / "tome-I.json"
STATE_FILE = ROOT / "data" / "production-state.json"
APPROVED_DIR = ROOT / "web" / "approved" / "Tome-I"
CANDIDATE_REBUILD_DIR = ROOT / "web" / "candidates" / "rebuild"
DISCARD_DIR = ROOT / "discard"
BACKUP_DIR = ROOT / "data" / "rebuild-backups"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def archive_remaining_approved() -> None:
    DISCARD_DIR.mkdir(parents=True, exist_ok=True)
    if not APPROVED_DIR.exists():
        return
    for source in APPROVED_DIR.glob("*.png"):
        target = DISCARD_DIR / source.name
        if target.exists():
            target = DISCARD_DIR / f"{source.stem}-{utc_stamp()}{source.suffix}"
        shutil.move(str(source), str(target))


def import_rebuild_source(page_id: str) -> str | None:
    source = DISCARD_DIR / f"{page_id}.png"
    if not source.exists():
        return None
    CANDIDATE_REBUILD_DIR.mkdir(parents=True, exist_ok=True)
    target = CANDIDATE_REBUILD_DIR / f"{page_id}-source.png"
    shutil.copy2(source, target)
    return target.relative_to(ROOT / "web").as_posix()


def main() -> int:
    tome = read_json(TOME_FILE)
    old_state = read_json(STATE_FILE)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"production-state-{utc_stamp()}.json"
    shutil.copy2(STATE_FILE, backup)

    archive_remaining_approved()

    pages = {}
    imported = []
    for page in tome["pages"]:
        page_id = page["page_id"]
        source = import_rebuild_source(page_id)
        entry = {
            "status": "planned",
            "attempt": 0,
            "current_candidate": None,
            "approved_candidate": None,
            "attempt_history": [],
            "review_notes": None,
        }
        if source:
            entry["rebuild_source_path"] = source
            imported.append(page_id)
        pages[page_id] = entry

    first_id = tome["pages"][0]["page_id"]
    first = pages[first_id]
    if first.get("rebuild_source_path"):
        candidate = {
            "candidate_id": f"{first_id}-REBUILD-SOURCE",
            "attempt": 1,
            "image_path": first["rebuild_source_path"],
            "qa_status": "imported_rebuild_source",
            "supervisor_status": "needs_human_review",
            "generation_mode": "rebuild_source",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        first["attempt"] = 1
        first["current_candidate"] = candidate
        first["attempt_history"] = [candidate]
        first["status"] = "awaiting_human"
    else:
        first["status"] = "queued"

    state = {
        "version": old_state.get("version", 1),
        "current_page_id": first_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "complete": False,
        "pages": pages,
    }
    write_json(STATE_FILE, state)

    print("Black-Ink Tome I rebuild reset complete.")
    print(f"Backup: {backup}")
    print(f"Imported discard sources: {len(imported)}")
    print(f"Current page: {first_id} ({first['status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
