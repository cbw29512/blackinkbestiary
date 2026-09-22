from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from catalog_audit import audit_monster_catalog
from series_readiness import audit_series


def main() -> int:
    catalog = audit_monster_catalog(ROOT)
    series = audit_series(ROOT)
    report = {"catalog": catalog, "series": series}
    print(json.dumps(report, indent=2))
    return 0 if catalog["pass"] and series["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
