from __future__ import annotations

from collections import Counter
from pathlib import Path

try:
    from .defect_taxonomy import load_taxonomy, record_defect_codes, taxonomy_labels
except ImportError:
    from defect_taxonomy import load_taxonomy, record_defect_codes, taxonomy_labels

ROOT = Path(__file__).resolve().parents[1]

SCOPE_RULES = {
    "IDENTITY_LIMB_COUNT": {
        "scopes": ["master_engine", "monster_family"],
        "master_lesson": "Strengthen universal exact topology/count checks and reject extra, missing, duplicated, merged, or branched appendages.",
        "monster_lesson": "Record this family-specific appendage drift as a known failure mode with the canonical limb/body count.",
    },
    "IDENTITY_HEROIC_BULK": {
        "scopes": ["monster_family"],
        "monster_lesson": "Strengthen family proportions and explicit anti-bodybuilder drift; preserve canonical size and mass.",
    },
    "IDENTITY_HORNS_TUSKS": {
        "scopes": ["monster_family"],
        "monster_lesson": "Record unwanted horns/tusks as family drift unless they are canonical anatomy.",
    },
    "IDENTITY_WRONG_CREATURE": {
        "scopes": ["monster_family", "master_engine"],
        "master_lesson": "Keep identity/body-plan verification ahead of scenery and fail closed on look-alike anatomy.",
        "monster_lesson": "Add the observed look-alike/body-plan drift to the family known-failure corrections.",
    },
    "ENVIRONMENT_GENERIC": {
        "scopes": ["master_engine", "page_recipe"],
        "master_lesson": "Require large structural environment proof before decorative detail.",
        "page_lesson": "Strengthen the page's unique landmark/framing/interaction evidence.",
    },
    "ACTION_UNCLEAR": {
        "scopes": ["master_engine", "page_recipe"],
        "master_lesson": "Require visible verb/contact/cause-and-effect proof rather than proximity.",
        "page_lesson": "Clarify the unique action relationship in the page recipe.",
    },
    "SWARM_WALLPAPER": {
        "scopes": ["master_engine", "monster_family"],
        "master_lesson": "Enforce universal swarm negative-space and controlled-population checks.",
        "monster_lesson": "Preserve family member scale/count and forbid wallpaper-density repetition.",
    },
    "SWARM_OVERSIZED_LEADER": {
        "scopes": ["master_engine", "monster_family"],
        "master_lesson": "Enforce equal-member scale for collective subjects.",
        "monster_lesson": "Record oversized-leader drift for swarm families.",
    },
    "QUALITY_DENSITY": {
        "scopes": ["master_engine"],
        "master_lesson": "Strengthen universal colorability checks for repeated micro-detail and tiny enclosed cells.",
    },
    "TECH_SAFE_MARGIN": {
        "scopes": ["master_engine"],
        "master_lesson": "Handle print-safe margins deterministically before QA.",
    },
    "TECH_COLOR_CONTAMINATION": {
        "scopes": ["master_engine"],
        "master_lesson": "Normalize accidental color deterministically before monochrome QA.",
    },
}


def build_learning_queue(records: list[dict], root: Path = ROOT) -> list[dict]:
    taxonomy = load_taxonomy(root / "config" / "defect_taxonomy.json")
    labels = taxonomy_labels(taxonomy)
    evidence: dict[str, Counter] = {}
    examples: dict[str, list[dict]] = {}

    for record in records:
        page_id = str(record.get("page_id") or "")
        for code in record_defect_codes(record, taxonomy):
            if code == "UNCLASSIFIED":
                continue
            evidence.setdefault(code, Counter())
            evidence[code][page_id or "<unknown>"] += 1
            examples.setdefault(code, []).append({
                "page_id": page_id,
                "stage": (record.get("visual_review") or {}).get("stage"),
                "defects": list((record.get("visual_review") or {}).get("defects") or []),
            })

    queue = []
    for code, pages in sorted(evidence.items(), key=lambda item: (-sum(item[1].values()), item[0])):
        rule = SCOPE_RULES.get(code, {"scopes": ["review_only"]})
        total = sum(pages.values())
        distinct_pages = len(pages)
        queue.append({
            "defect_code": code,
            "label": (labels.get(code) or {}).get("label"),
            "evidence_count": total,
            "distinct_pages": distinct_pages,
            "scope": list(rule.get("scopes") or []),
            "master_engine_lesson": rule.get("master_lesson"),
            "monster_family_lesson": rule.get("monster_lesson"),
            "page_recipe_lesson": rule.get("page_lesson"),
            "priority": "high" if distinct_pages >= 2 or total >= 3 else "normal",
            "auto_apply": False,
            "reason": "Lessons are queued for evidence-driven engine/family/page updates; raw reviewer text never rewrites authority automatically.",
            "examples": examples.get(code, [])[:3],
        })
    return queue
