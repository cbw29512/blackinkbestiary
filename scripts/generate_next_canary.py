from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from next_canary_target import current_target


def main() -> int:
    payload = current_target(ROOT)
    if payload["complete"]:
        print("ONE-AT-A-TIME CANARY: all configured pages are human approved.")
        return 0

    target = payload["target"]
    page_id = str(target["page_id"])
    state = str(target["state"])
    if state == "awaiting_review":
        print(
            f"ONE-AT-A-TIME CANARY: {page_id} is waiting for human review; "
            "no later page may generate."
        )
        return 20
    if state != "needs_generation":
        print(f"ONE-AT-A-TIME CANARY: unsupported target state {state!r} for {page_id}.")
        return 2

    print(
        f"ONE-AT-A-TIME CANARY: generating only {page_id}; "
        "all later Canary pages remain blocked until human approval."
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_test_gallery.py"),
            "--only",
            page_id,
            "--candidate",
            "1",
            "--copies",
            "1",
            "--rerun-failed",
        ],
        cwd=ROOT,
        check=False,
    )
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
