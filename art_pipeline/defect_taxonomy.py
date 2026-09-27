from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_PATH = ROOT / "config" / "defect_taxonomy.json"


def load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_text(text: str, taxonomy: dict | None = None) -> list[str]:
    value = str(text or "").strip()
    if not value:
        return []
    cfg = taxonomy or load_taxonomy()
    matches = []
    for rule in cfg.get("rules", []):
        if any(re.search(pattern, value, re.IGNORECASE) for pattern in rule.get("patterns", [])):
            matches.append(str(rule["code"]))
    if matches:
        return sorted(set(matches))
    fallback = (cfg.get("fallback") or {}).get("code")
    return [str(fallback)] if fallback else []


def record_defect_codes(item: dict, taxonomy: dict | None = None) -> list[str]:
    cfg = taxonomy or load_taxonomy()
    texts = []
    status = str(item.get("status") or "").strip()
    error = str(item.get("error") or "").strip()
    if status:
        texts.append(status)
    if error:
        texts.append(error)

    visual = item.get("visual_review") or {}
    texts.extend(str(value) for value in visual.get("defects") or [] if str(value).strip())

    assistant = item.get("assistant_review") or {}
    notes = str(assistant.get("notes") or "").strip()
    if notes:
        texts.append(notes)

    codes = set()
    for text in texts:
        codes.update(classify_text(text, cfg))
    if len(codes) > 1:
        codes.discard("UNCLASSIFIED")
    return sorted(codes)


def count_defects(records: list[dict], taxonomy: dict | None = None) -> dict[str, int]:
    cfg = taxonomy or load_taxonomy()
    counts: Counter[str] = Counter()
    for item in records:
        counts.update(record_defect_codes(item, cfg))
    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def taxonomy_labels(taxonomy: dict | None = None) -> dict[str, dict]:
    cfg = taxonomy or load_taxonomy()
    result = {
        str(rule["code"]): {
            "category": rule.get("category"),
            "label": rule.get("label"),
        }
        for rule in cfg.get("rules", [])
    }
    fallback = cfg.get("fallback") or {}
    if fallback.get("code"):
        result[str(fallback["code"])] = {
            "category": fallback.get("category"),
            "label": fallback.get("label"),
        }
    return result
