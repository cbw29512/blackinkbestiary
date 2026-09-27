from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

try:
    from .defect_taxonomy import load_taxonomy, record_defect_codes, taxonomy_labels
except ImportError:
    from defect_taxonomy import load_taxonomy, record_defect_codes, taxonomy_labels

ROOT = Path(__file__).resolve().parents[1]


def _production_page_families(root: Path) -> dict[str, str]:
    series = json.loads((root / "data" / "series.json").read_text(encoding="utf-8"))
    book = next(
        (
            row for row in series.get("books", [])
            if str(row.get("status") or "").lower() == "production"
        ),
        None,
    )
    if not book:
        return {}
    manifest_path = root / str(book.get("manifest_path") or "")
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = {}
    for page in manifest.get("pages", []):
        page_id = str(page.get("page_id") or "")
        spec_id = str(page.get("monster_spec_id") or "")
        if not page_id or not spec_id:
            continue
        spec_path = root / "data" / "monsters" / f"{spec_id}.json"
        if not spec_path.exists():
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        family = str(
            spec.get("family_profile")
            or spec.get("family")
            or spec.get("monster_id")
            or spec_id
        )
        result[page_id] = family
    return result


def _evidence_text(record: dict) -> list[str]:
    visual = record.get("visual_review") or {}
    defects = [
        str(value).strip()
        for value in visual.get("defects") or []
        if str(value).strip()
    ]
    if defects:
        return defects
    assistant = record.get("assistant_review") or {}
    notes = str(assistant.get("notes") or "").strip()
    if notes:
        return [notes]
    error = str(record.get("error") or "").strip()
    if error:
        return [error]
    status = str(record.get("status") or "").strip()
    return [status] if status else []


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


def learning_observations(records: list[dict]) -> list[dict]:
    """Expand each candidate into distinct review observations without double-counting."""
    observations = []
    for record in records:
        page_id = str(record.get("page_id") or "")
        candidate = int(record.get("candidate") or 0)

        # Preserve top-level technical/assistant evidence, but if pass_history
        # exists do not also count visual_review because it mirrors the final pass.
        base = {
            "page_id": page_id,
            "candidate": candidate,
            "status": record.get("status"),
            "error": record.get("error"),
            "assistant_review": record.get("assistant_review"),
            "visual_review": (
                None if record.get("pass_history") else record.get("visual_review")
            ),
            "evidence_source": "candidate_record",
        }
        observations.append(base)

        for step in record.get("pass_history") or []:
            review = step.get("review") or {}
            if not review:
                continue
            observations.append({
                "page_id": page_id,
                "candidate": candidate,
                "pass": step.get("pass"),
                "visual_review": review,
                "evidence_source": "refinement_pass",
            })
    return observations


def build_learning_queue(records: list[dict], root: Path = ROOT) -> list[dict]:
    taxonomy = load_taxonomy(root / "config" / "defect_taxonomy.json")
    labels = taxonomy_labels(taxonomy)
    evidence: dict[str, Counter] = {}
    family_evidence: dict[str, set[str]] = {}
    examples: dict[str, list[dict]] = {}
    page_families = _production_page_families(root)

    for record in learning_observations(records):
        page_id = str(record.get("page_id") or "")
        for code in record_defect_codes(record, taxonomy):
            if code == "UNCLASSIFIED":
                continue
            evidence.setdefault(code, Counter())
            evidence[code][page_id or "<unknown>"] += 1
            family = page_families.get(page_id)
            if family:
                family_evidence.setdefault(code, set()).add(family)
            examples.setdefault(code, []).append({
                "page_id": page_id,
                "candidate": record.get("candidate"),
                "pass": record.get("pass"),
                "evidence_source": record.get("evidence_source"),
                "stage": (record.get("visual_review") or {}).get("stage"),
                "evidence_text": _evidence_text(record),
            })

    queue = []
    for code, pages in sorted(evidence.items(), key=lambda item: (-sum(item[1].values()), item[0])):
        rule = SCOPE_RULES.get(code, {"scopes": ["review_only"]})
        total = sum(pages.values())
        distinct_pages = len(pages)
        distinct_families = len(family_evidence.get(code) or set())
        scopes = list(rule.get("scopes") or [])
        master_lesson = rule.get("master_lesson")
        if distinct_families >= 3 and "master_engine" not in scopes:
            scopes.append("master_engine")
            master_lesson = master_lesson or (
                "This defect now spans multiple monster families; inspect and strengthen "
                "the universal generation/review contract while preserving family-specific data."
            )
        queue.append({
            "defect_code": code,
            "label": (labels.get(code) or {}).get("label"),
            "evidence_count": total,
            "distinct_pages": distinct_pages,
            "distinct_families": distinct_families,
            "scope": scopes,
            "master_engine_lesson": master_lesson,
            "monster_family_lesson": rule.get("monster_lesson"),
            "page_recipe_lesson": rule.get("page_lesson"),
            "priority": "high" if distinct_pages >= 2 or total >= 3 else "normal",
            "auto_apply": False,
            "reason": "Lessons are queued for evidence-driven engine/family/page updates; raw reviewer text never rewrites authority automatically.",
            "examples": examples.get(code, [])[:3],
        })
    return queue
