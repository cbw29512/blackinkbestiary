from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from catalog_audit import audit_monster_catalog
from page_recipe_audit import audit_manifest_recipe_debt
from series_readiness import audit_series


def main() -> int:
    catalog = audit_monster_catalog(ROOT)
    series = audit_series(ROOT)
    page_recipe_migration = audit_manifest_recipe_debt(
        ROOT,
        ROOT / "data" / "tome-I.json",
    )
    report = {
        "catalog": catalog,
        "series": series,
        "page_recipe_migration": page_recipe_migration,
    }
    print(json.dumps(report, indent=2))
    return 0 if catalog["pass"] and series["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
