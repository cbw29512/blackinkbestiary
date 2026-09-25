from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "art_pipeline"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def forbidden_engine_literals(root: Path = ROOT) -> dict[str, str]:
    terms: dict[str, str] = {}

    monster_dir = root / "data" / "monsters"
    for path in sorted(monster_dir.glob("*.json")):
        spec = _read(path)
        spec_id = str(spec.get("monster_id") or path.stem).strip()
        display = str(spec.get("display_name") or "").strip()
        if spec_id:
            terms[spec_id.lower()] = f"monster_id:{spec_id}"
        if display and len(display) >= 5:
            terms[display.lower()] = f"monster_name:{display}"

    series = _read(root / "data" / "series.json")
    for book in series.get("books", []):
        manifest_path = root / str(book.get("manifest_path") or "")
        if not manifest_path.exists():
            continue
        manifest = _read(manifest_path)
        for page in manifest.get("pages", []):
            page_id = str(page.get("page_id") or "").strip()
            if page_id:
                terms[page_id.lower()] = f"page_id:{page_id}"

    return terms


def audit_master_engine_separation(root: Path = ROOT) -> dict:
    """Fail if generic engine Python contains literal monster/page special cases."""
    forbidden = forbidden_engine_literals(root)
    violations = []

    for path in sorted((root / "art_pipeline").glob("*.py")):
        if path.name == "master_engine_guard.py":
            continue
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for literal, label in forbidden.items():
            # Require token-ish boundaries so short fragments do not create noise.
            pattern = r"(?<![a-z0-9_])" + re.escape(literal) + r"(?![a-z0-9_])"
            match = re.search(pattern, lowered)
            if not match:
                continue
            line = text.count("\n", 0, match.start()) + 1
            violations.append({
                "path": path.relative_to(root).as_posix(),
                "line": line,
                "authority": label,
                "literal": literal,
            })

    return {
        "schema_version": 1,
        "pass": not violations,
        "engine_scope": "art_pipeline/*.py",
        "forbidden_literal_count": len(forbidden),
        "violations": violations,
        "rule": (
            "Master engine code may consume monster/page data generically but may not "
            "contain literal monster IDs, monster display names, or production page IDs."
        ),
    }
