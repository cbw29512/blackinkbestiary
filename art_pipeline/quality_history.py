from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from .defect_taxonomy import count_defects, load_taxonomy, taxonomy_labels
    from .learning_feedback import build_learning_queue
    from .master_engine_guard import audit_master_engine_separation
    from .production_audit import audit_active_book
    from .prompt_load import prompt_load_report
    from .replication_probe import run_replication_probe
    from .series_readiness import audit_series
except ImportError:
    from defect_taxonomy import count_defects, load_taxonomy, taxonomy_labels
    from learning_feedback import build_learning_queue
    from master_engine_guard import audit_master_engine_separation
    from production_audit import audit_active_book
    from prompt_load import prompt_load_report
    from replication_probe import run_replication_probe
    from series_readiness import audit_series

ROOT = Path(__file__).resolve().parents[1]

IMAGE_TECHNICAL_FAILURE_STATUSES = {
    "technical_qa_failed",
    "technical_qa_stalled",
    "failed",
}

REVIEW_PIPELINE_FAILURE_STATUSES = {
    "vision_reviewer_failed",
    "failed",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(100.0 * numerator / denominator, 1)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_scorecard(root: Path = ROOT) -> dict:
    return _read(root / "config" / "quality_scorecard.json")


def quality_contract_fingerprint(root: Path = ROOT, config: dict | None = None) -> str:
    cfg = config or load_scorecard(root)
    digest = hashlib.sha256()
    for relative in cfg.get("comparison_authority_paths", []):
        path = root / relative
        digest.update(str(relative).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes() if path.exists() else b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def evaluate_readiness(
    metrics: dict,
    required_categories: list[str],
    blockers: list[str] | None = None,
) -> dict:
    blockers = list(blockers or [])
    missing = [name for name in required_categories if name not in metrics]
    values = [
        float(metrics.get(name, 0.0))
        for name in required_categories
    ]
    overall = round(sum(values) / len(values), 1) if values else 0.0
    floor = min(values) if values else 0.0
    weakest = (
        min(required_categories, key=lambda name: float(metrics.get(name, 0.0)))
        if required_categories else None
    )
    automated_100 = (
        not missing
        and not blockers
        and bool(required_categories)
        and all(float(metrics.get(name, 0.0)) == 100.0 for name in required_categories)
    )
    return {
        "overall_automated_readiness": overall,
        "readiness_floor": floor,
        "weakest_metric": weakest,
        "missing_required_categories": missing,
        "known_blockers": blockers,
        "automated_100": automated_100,
    }


def latest_records(state: dict) -> list[dict]:
    """Latest record for every historical page/candidate pair."""
    latest = {}
    for item in state.get("results", []):
        page_id = str(item.get("page_id") or "")
        candidate = int(item.get("candidate") or 0)
        if not page_id or candidate < 1:
            continue
        latest[(page_id, candidate)] = item
    return list(latest.values())


def current_page_records(state: dict, page_ids: list[str]) -> list[dict]:
    """Current authoritative record for each requested page.

    Human/assistant selections win when present. Otherwise use the last record
    written for the page, which is the current autopilot attempt. Historical
    candidates remain in state for learning but never inflate current defects.
    """
    wanted = set(page_ids)
    by_page: dict[str, list[dict]] = {page_id: [] for page_id in page_ids}
    for item in state.get("results", []):
        page_id = str(item.get("page_id") or "")
        if page_id in wanted and int(item.get("candidate") or 0) > 0:
            by_page[page_id].append(item)

    selections = state.get("selections") or {}
    result = []
    for page_id in page_ids:
        rows = by_page.get(page_id) or []
        if not rows:
            continue
        selected_candidate = int((selections.get(page_id) or {}).get("candidate") or 0)
        if selected_candidate:
            selected_rows = [
                item for item in rows
                if int(item.get("candidate") or 0) == selected_candidate
            ]
            if selected_rows:
                result.append(selected_rows[-1])
                continue
        result.append(rows[-1])
    return result


def canary_metrics(state: dict, canary_page_ids: list[str]) -> dict:
    current = {
        str(item.get("page_id") or ""): item
        for item in current_page_records(state, canary_page_ids)
    }
    rows = []
    technical_passes = review_pipeline_passes = visual_passes = semantic_passes = all_passes = 0

    for page_id in canary_page_ids:
        item = current.get(page_id) or {}
        status = str(item.get("status") or "missing")
        visual = item.get("visual_review") or {}
        assistant = item.get("assistant_review") or {}

        technical = bool(item) and status not in IMAGE_TECHNICAL_FAILURE_STATUSES
        review_pipeline = bool(item) and status not in REVIEW_PIPELINE_FAILURE_STATUSES
        decision = str(assistant.get("decision") or "").strip().lower()
        exact_image_approved = decision in {"approve", "select"}

        # Local VLM output is advisory telemetry only. Required readiness
        # metrics must never be satisfied by a local score/stage/pass.
        visual_clean = exact_image_approved
        semantic = exact_image_approved

        passes_all = technical and visual_clean and semantic
        technical_passes += int(technical)
        review_pipeline_passes += int(review_pipeline)
        visual_passes += int(visual_clean)
        semantic_passes += int(semantic)
        all_passes += int(passes_all)
        rows.append({
            "page_id": page_id,
            "status": status,
            "technical_pass": technical,
            "review_pipeline_pass": review_pipeline,
            "visual_cleanliness_pass": visual_clean,
            "semantic_accuracy_pass": semantic,
            "all_automated_gates_pass": passes_all,
            "visual_stage": visual.get("stage"),
            "visual_score": visual.get("score"),
            "local_visual_advisory_pass": bool(visual.get("pass")),
            "assistant_decision": assistant.get("decision"),
        })

    total = len(canary_page_ids)
    return {
        "total": total,
        "technical_passes": technical_passes,
        "review_pipeline_passes": review_pipeline_passes,
        "visual_passes": visual_passes,
        "semantic_passes": semantic_passes,
        "all_passes": all_passes,
        "technical_qa": _pct(technical_passes, total),
        "review_pipeline_health": _pct(review_pipeline_passes, total),
        "visual_cleanliness": _pct(visual_passes, total),
        "semantic_accuracy": _pct(semantic_passes, total),
        "all_automated_gates": _pct(all_passes, total),
        "rows": rows,
    }


def generation_efficiency(
    state: dict,
    canary_page_ids: list[str],
    canary: dict | None = None,
) -> dict:
    current = current_page_records(state, canary_page_ids)
    gpu_attempts = 0
    refinement_passes = 0
    max_refinement_pages = 0
    semantic_stalled_pages = 0

    for item in current:
        history = item.get("pass_history") or []
        attempts = len(history)
        if attempts == 0 and str(item.get("status") or "") not in {"", "missing"}:
            attempts = 1
        gpu_attempts += attempts
        refinement_passes += max(0, attempts - 1)
        status = str(item.get("status") or "")
        if status == "max_refinements_reached":
            max_refinement_pages += 1
        if status == "semantic_stalled":
            semantic_stalled_pages += 1

    page_count = len(current)
    metrics = canary or canary_metrics(state, canary_page_ids)
    semantic_passes = int(metrics.get("semantic_passes") or 0)
    all_passes = int(metrics.get("all_passes") or 0)

    return {
        "pages_considered": page_count,
        "gpu_attempts": gpu_attempts,
        "refinement_passes": refinement_passes,
        "pages_at_max_refinements": max_refinement_pages,
        "pages_semantic_stalled": semantic_stalled_pages,
        "avg_gpu_attempts_per_page": (
            round(gpu_attempts / page_count, 2) if page_count else None
        ),
        "gpu_attempts_per_semantic_pass": (
            round(gpu_attempts / semantic_passes, 2) if semantic_passes else None
        ),
        "semantic_yield_percent": _pct(semantic_passes, gpu_attempts),
        "all_gate_yield_percent": _pct(all_passes, gpu_attempts),
    }


def _generic_assembly_exists(root: Path) -> bool:
    candidates = (
        "art_pipeline/book_assembly.py",
        "scripts/assemble_book.py",
        "scripts/export_kdp_interior.py",
    )
    return any((root / relative).exists() for relative in candidates)


def print_package_report(root: Path = ROOT) -> dict:
    qa_path = root / "art_pipeline" / "qa.py"
    png_path = root / "art_pipeline" / "png_content_qa.py"
    qa_text = qa_path.read_text(encoding="utf-8") if qa_path.exists() else ""
    png_text = png_path.read_text(encoding="utf-8") if png_path.exists() else ""
    proof_candidates = (
        root / "build" / "final-interior.pdf",
        root / "output" / "final-interior.pdf",
        root / "web" / "final-interior.pdf",
    )
    components = {
        "kdp_standard": (root / "config" / "kdp_print_standard.json").exists(),
        "exact_export_qa": "def inspect_kdp_export" in qa_text,
        "deterministic_safe_margin": "def enforce_print_safe_margin" in png_text,
        "generic_assembly_pipeline": _generic_assembly_exists(root),
        "reproducible_final_proof": any(path.exists() for path in proof_candidates),
    }
    weights = {
        "kdp_standard": 20,
        "exact_export_qa": 20,
        "deterministic_safe_margin": 15,
        "generic_assembly_pipeline": 25,
        "reproducible_final_proof": 20,
    }
    score = sum(weights[name] for name, passed in components.items() if passed)
    return {"score": score, "components": components}


def replication_report(root: Path, series_report: dict) -> dict:
    future = [row for row in series_report.get("books", []) if row.get("book_id") != "TOME-I"]
    contracts = (
        "config/universal_page_contract.json",
        "config/universal_monster_contract.json",
        "config/universal_environment_contract.json",
        "config/universal_story_contract.json",
    )
    probe = run_replication_probe(root)
    separation = audit_master_engine_separation(root)
    components = {
        "universal_contracts": all((root / path).exists() for path in contracts),
        "generic_book_scaffolding": (root / "scripts" / "scaffold_book.py").exists() and (root / "art_pipeline" / "book_scaffold.py").exists(),
        "series_audit_green": bool(series_report.get("pass")),
        "eight_books_registered": int(series_report.get("books_registered") or 0) >= 8,
        "future_book_plans": bool(future) and all(bool(row.get("plan_exists")) for row in future),
        "generic_assembly_pipeline": _generic_assembly_exists(root),
        "synthetic_replication_test": (root / "tests" / "test_replication_readiness.py").exists(),
        "synthetic_pipeline_probe": bool(probe.get("pass")),
        "master_engine_data_separation": bool(separation.get("pass")),
    }
    weights = {
        "universal_contracts": 15,
        "generic_book_scaffolding": 10,
        "series_audit_green": 10,
        "eight_books_registered": 5,
        "future_book_plans": 5,
        "generic_assembly_pipeline": 15,
        "synthetic_replication_test": 5,
        "synthetic_pipeline_probe": 25,
        "master_engine_data_separation": 10,
    }
    score = sum(weights[name] for name, passed in components.items() if passed)
    return {
        "score": score,
        "components": components,
        "synthetic_pipeline_probe": probe,
        "master_engine_data_separation": separation,
    }


def _book_locked_progress(root: Path, row: dict) -> tuple[int, float]:
    series = _read(root / "data" / "series.json")
    book = next((item for item in series.get("books", []) if item.get("book_id") == row.get("book_id")), None)
    if not book:
        return 0, 0.0
    state_path = root / str(book.get("state_path") or "")
    if not state_path.exists() or not state_path.is_file():
        return 0, 0.0
    state = _read(state_path)
    locked = sum(1 for entry in (state.get("pages") or {}).values() if entry.get("status") == "locked")
    target = int(row.get("target_pages") or 0)
    return locked, _pct(locked, target)


def build_quality_snapshot(
    root: Path,
    state: dict,
    runtime: dict | None,
    engine_preflight: dict | None,
    engine_commit: str,
    autopilot: dict | None = None,
) -> dict:
    scorecard = load_scorecard(root)
    series = audit_series(root)
    active = audit_active_book(root)
    active_book_id = str(active.get("book_id") or "")
    canary_ids = list(scorecard.get("canary_page_ids") or [])
    canary = canary_metrics(state, canary_ids)
    efficiency = generation_efficiency(state, canary_ids, canary)
    prompt_load = prompt_load_report(root, canary_ids)
    print_report = print_package_report(root)
    replication = replication_report(root, series)

    runtime_ready = str((runtime or {}).get("status") or "").lower() == "ready"
    preflight_ready = str((engine_preflight or {}).get("status") or "").lower() in {"passed", "pass", "success"}
    heartbeat_status = str((autopilot or {}).get("status") or "").lower()
    heartbeat_phase = str((autopilot or {}).get("phase") or "").lower()
    heartbeat_commit = str((autopilot or {}).get("engine_commit") or "")
    autopilot_ready = bool(
        autopilot
        and heartbeat_status in {"running", "ready"}
        and heartbeat_phase not in {"failed", "blocked"}
        and heartbeat_commit == engine_commit
    )
    foundation_components = {
        "local_runtime_ready": runtime_ready,
        "engine_preflight_passed": preflight_ready,
        "series_audit_green": bool(series.get("pass")),
        "active_book_structure_valid": bool(active.get("pass")),
        "autopilot_heartbeat_current": autopilot_ready,
    }
    foundation = 20 * sum(1 for value in foundation_components.values() if value)

    required_categories = list(scorecard.get("required_categories") or [])
    books = []
    for row in series.get("books", []):
        target = int(row.get("target_pages") or 0)
        recipe_ready = int(row.get("recipe_ready") or 0)
        completeness = _pct(recipe_ready, target)
        locked_count, locked_progress = _book_locked_progress(root, row)
        is_active = str(row.get("book_id") or "") == active_book_id
        metrics = {
            "foundation_readiness": float(foundation),
            "technical_qa_pass_rate": canary["technical_qa"] if is_active else 0.0,
            "review_pipeline_health": canary["review_pipeline_health"] if is_active else 0.0,
            "visual_cleanliness": canary["visual_cleanliness"] if is_active else 0.0,
            "semantic_accuracy": canary["semantic_accuracy"] if is_active else 0.0,
            "completeness": completeness,
            "print_package_readiness": float(print_report["score"]),
            "locked_page_progress": locked_progress,
            "replication_readiness": float(replication["score"]),
        }
        readiness = evaluate_readiness(metrics, required_categories)
        books.append({
            "book_id": row.get("book_id"),
            "title": row.get("title"),
            "active": is_active,
            "target_pages": target,
            "recipe_ready": recipe_ready,
            "locked_pages": locked_count,
            "metrics": metrics,
            **readiness,
        })

    taxonomy = load_taxonomy(root / "config" / "defect_taxonomy.json")
    current_records = current_page_records(state, canary_ids)
    historical_records = latest_records(state)
    defects = count_defects(current_records, taxonomy)
    historical_defects = count_defects(historical_records, taxonomy)
    learning_queue = build_learning_queue(historical_records, root)
    status_counts = Counter(str(item.get("status") or "unknown") for item in current_records)
    historical_status_counts = Counter(
        str(item.get("status") or "unknown") for item in historical_records
    )
    active_blockers = [code for code, count in defects.items() if count > 0]
    for book in books:
        blockers = active_blockers if book.get("active") else []
        book.update(evaluate_readiness(
            book.get("metrics") or {},
            required_categories,
            blockers,
        ))

    active_row = next((book for book in books if book["active"]), None)
    active_metrics = dict((active_row or {}).get("metrics") or {})
    series_score = min(
        (float(book.get("overall_automated_readiness") or 0.0) for book in books),
        default=0.0,
    )
    series_readiness_floor = min(
        (float(book.get("readiness_floor") or 0.0) for book in books),
        default=0.0,
    )
    series_automated_100 = bool(books) and all(
        bool(book.get("automated_100")) for book in books
    )

    snapshot = {
        "schema_version": 1,
        "quality_contract_version": scorecard.get("contract_version"),
        "quality_contract_fingerprint": quality_contract_fingerprint(root, scorecard),
        "measured_at": utc_now(),
        "engine_commit": engine_commit,
        "active_book_id": active_book_id,
        "metrics": active_metrics,
        "overall_automated_readiness": (active_row or {}).get("overall_automated_readiness", 0.0),
        "readiness_floor": (active_row or {}).get("readiness_floor", 0.0),
        "series_score": series_score,
        "series_readiness_floor": series_readiness_floor,
        "series_automated_100": series_automated_100,
        "canary": canary,
        "generation_efficiency": efficiency,
        "prompt_load": prompt_load,
        "books": books,
        "foundation_components": foundation_components,
        "print_package": print_report,
        "replication": replication,
        "defect_counts": defects,
        "historical_defect_counts": historical_defects,
        "learning_queue": learning_queue,
        "defect_labels": taxonomy_labels(taxonomy),
        "status_counts": dict(sorted(status_counts.items())),
        "historical_status_counts": dict(sorted(historical_status_counts.items())),
        "known_blockers": active_blockers,
    }
    fingerprint_payload = dict(snapshot)
    fingerprint_payload.pop("measured_at", None)
    snapshot["measurement_fingerprint"] = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return snapshot
