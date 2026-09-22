from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from production_audit import audit_active_book


def main() -> int:
    try:
        report = audit_active_book(ROOT)
    except Exception as exc:
        print(f"PRODUCTION AUDIT FAILED: {exc}")
        return 2

    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
