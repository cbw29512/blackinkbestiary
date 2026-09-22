from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from book_registry import series_status


def main() -> int:
    rows = series_status(ROOT)
    print(json.dumps(rows, indent=2))
    ready = sum(1 for row in rows if row["production_files_complete"])
    print(f"\nSeries: {len(rows)} books registered; {ready} currently has production files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
