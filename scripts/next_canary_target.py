from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))
sys.path.insert(0, str(ROOT / "scripts"))

from canary_autopilot_status import (
    classify,
    configured_canary_page_ids,
    load_canary_pages,
)
from generation_fingerprint import page_generation_fingerprint, page_review_fingerprint

STATE = ROOT / "data" / "test-gallery-state.json"


def current_target(root: Path = ROOT) -> dict:
    page_ids = configured_canary_page_ids(root)
    pages = load_canary_pages(root)
    state = {"results": []}
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))
    results = {
        (str(item.get("page_id")), int(item.get("candidate") or 0)): item
        for item in state.get("results", [])
    }

    rows = []
    for page_id in page_ids:
        item = results.get((page_id, 1))
        page = pages.get(page_id)
        generation_fp = page_generation_fingerprint(page, root) if page else None
        review_fp = page_review_fingerprint(page, root) if page else None
        status = classify(
            item,
            root,
            current_generation_fingerprint=generation_fp,
            current_review_fingerprint=review_fp,
        )
        row = {
            "page_id": page_id,
            "monster_name": (page or {}).get("monster_name"),
            "state": status,
            "raw_status": str((item or {}).get("status") or "missing"),
            "candidate": 1,
        }
        rows.append(row)
        if status != "approved":
            return {
                "complete": False,
                "target": row,
                "rows": rows,
            }

    return {"complete": True, "target": None, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Find the next unresolved human Canary page")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = current_target(ROOT)
    if args.json:
        print(json.dumps(payload))
    elif payload["complete"]:
        print("CANARY CALIBRATION COMPLETE: all configured pages are human approved.")
    else:
        target = payload["target"]
        print(
            f"NEXT CANARY: {target['page_id']} - {target.get('monster_name') or ''} "
            f"state={target['state']} raw={target['raw_status']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
