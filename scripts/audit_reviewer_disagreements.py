from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from reviewer_audit import audit_files

MANIFEST = ROOT / "review-previews" / "manifest.json"
DECISIONS = ROOT / "review-previews" / "decisions.json"


def main() -> int:
    if not MANIFEST.exists():
        raise SystemExit(f"Missing review manifest: {MANIFEST}")
    if not DECISIONS.exists():
        raise SystemExit(f"Missing review decisions: {DECISIONS}")

    report = audit_files(MANIFEST, DECISIONS)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
