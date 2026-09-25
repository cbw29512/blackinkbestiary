from __future__ import annotations

import json
from pathlib import Path


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def reviewer_disagreement_report(manifest: dict, decisions: dict) -> dict:
    """Compare local advisory verdicts to exact-image authority by review_id only.

    Page/candidate labels are intentionally insufficient: a disagreement counts
    only when both systems judged the exact same image hash represented by the
    same review_id.
    """
    decision_by_id = {}
    for row in decisions.get("reviews") or []:
        review_id = str(row.get("review_id") or "").strip()
        decision = str(row.get("decision") or "").strip().lower()
        if review_id and decision in {"approve", "select", "reject"}:
            decision_by_id[review_id] = row

    matched = []
    false_positives = []
    false_negatives = []
    agreements = []

    for candidate in manifest.get("candidates") or []:
        review_id = str(candidate.get("review_id") or "").strip()
        authority = decision_by_id.get(review_id)
        if not review_id or authority is None:
            continue

        visual = candidate.get("visual_review") or {}
        local_pass = bool(visual.get("pass"))
        decision = str(authority.get("decision") or "").strip().lower()
        authority_pass = decision in {"approve", "select"}

        row = {
            "review_id": review_id,
            "page_id": candidate.get("page_id"),
            "candidate": candidate.get("candidate"),
            "source_sha256": candidate.get("source_sha256"),
            "local_pass": local_pass,
            "local_score": visual.get("score"),
            "local_stage": visual.get("stage"),
            "authority_decision": decision,
            "authority_notes": authority.get("notes"),
        }
        matched.append(row)

        if local_pass and not authority_pass:
            false_positives.append(row)
        elif not local_pass and authority_pass:
            false_negatives.append(row)
        else:
            agreements.append(row)

    total = len(matched)
    return {
        "schema_version": 1,
        "exact_image_matches": total,
        "agreements": len(agreements),
        "local_false_positives": len(false_positives),
        "local_false_negatives": len(false_negatives),
        "agreement_rate": round(100.0 * len(agreements) / total, 1) if total else None,
        "false_positive_rate": (
            round(100.0 * len(false_positives) / total, 1) if total else None
        ),
        "false_negative_rate": (
            round(100.0 * len(false_negatives) / total, 1) if total else None
        ),
        "false_positive_rows": false_positives,
        "false_negative_rows": false_negatives,
        "matched_rows": matched,
        "rule": (
            "Reviewer disagreement is measured only for identical review_id/image hashes; "
            "same page or candidate numbers across different generations do not count."
        ),
    }


def audit_files(manifest_path: Path, decisions_path: Path) -> dict:
    return reviewer_disagreement_report(_read(manifest_path), _read(decisions_path))
