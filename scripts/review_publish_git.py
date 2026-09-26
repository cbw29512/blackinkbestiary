from __future__ import annotations

import json
import subprocess
from pathlib import Path

from review_publish_worktree import publish_snapshot_once

REVIEW_BRANCH = "review-previews-live"
DECISIONS_RELATIVE = "review-previews/decisions.json"
QUALITY_CURRENT_RELATIVE = "review-previews/quality-current.json"
QUALITY_HISTORY_RELATIVE = "review-previews/quality-history.jsonl"
QUALITY_TREND_RELATIVE = "review-previews/quality-trend.json"


def run(root: Path, *args: str) -> None:
    subprocess.run(args, cwd=root, check=True)


def output(root: Path, *args: str) -> str:
    return subprocess.check_output(args, cwd=root, text=True).strip()


def tracked_changes_outside_previews(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    outside = []
    for raw in result.stdout.splitlines():
        path = raw[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if not path.startswith("review-previews/"):
            outside.append(raw)
    return outside


def _sync_optional_history(root: Path, remote_ref: str) -> None:
    path = root / QUALITY_HISTORY_RELATIVE
    try:
        payload = output(root, "git", "show", f"{remote_ref}:{QUALITY_HISTORY_RELATIVE}")
    except subprocess.CalledProcessError:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((payload.rstrip() + "\n") if payload.strip() else "", encoding="utf-8")


def sync_live_decisions(root: Path) -> str:
    """Copy live review decisions and quality history into the next snapshot."""
    run(
        root,
        "git",
        "fetch",
        "origin",
        f"+{REVIEW_BRANCH}:refs/remotes/origin/{REVIEW_BRANCH}",
    )
    remote_ref = f"origin/{REVIEW_BRANCH}"
    live_head = output(root, "git", "rev-parse", remote_ref)
    payload = output(root, "git", "show", f"{remote_ref}:{DECISIONS_RELATIVE}")
    parsed = json.loads(payload)
    reviews = parsed.get("reviews") if isinstance(parsed, dict) else None
    if not isinstance(reviews, list):
        raise RuntimeError("Live review decisions are missing a reviews list.")

    path = root / DECISIONS_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")
    _sync_optional_history(root, remote_ref)
    return live_head


def _load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def _signed(value: float) -> str:
    return f"{value:+.1f}"


def append_quality_snapshot(root: Path) -> bool:
    current_path = root / QUALITY_CURRENT_RELATIVE
    if not current_path.exists():
        return False

    current = json.loads(current_path.read_text(encoding="utf-8"))
    history_path = root / QUALITY_HISTORY_RELATIVE
    trend_path = root / QUALITY_TREND_RELATIVE
    history = _load_history(history_path)
    previous = next(
        (
            item for item in reversed(history)
            if item.get("active_book_id") == current.get("active_book_id")
        ),
        None,
    )

    comparable = bool(
        previous
        and previous.get("quality_contract_fingerprint")
        == current.get("quality_contract_fingerprint")
    )
    reason = None
    if previous and not comparable:
        reason = "quality contract changed; new baseline established"
    elif not previous:
        reason = "first recorded baseline for active book"

    comparisons = {}
    defect_comparisons = {}
    efficiency_comparisons = {}
    if comparable:
        previous_metrics = previous.get("metrics") or {}
        for name, value in (current.get("metrics") or {}).items():
            old = previous_metrics.get(name)
            if not isinstance(value, (int, float)) or not isinstance(old, (int, float)):
                continue
            delta = round(float(value) - float(old), 1)
            comparisons[name] = {
                "previous": old,
                "current": value,
                "delta": delta,
                "signed_delta": _signed(delta),
                "trend": "improving" if delta > 0 else "regressing" if delta < 0 else "flat",
                "higher_is_better": True,
            }

        current_defects = current.get("defect_counts") or {}
        previous_defects = previous.get("defect_counts") or {}
        for code in sorted(set(current_defects) | set(previous_defects)):
            now = int(current_defects.get(code) or 0)
            old = int(previous_defects.get(code) or 0)
            delta = now - old
            defect_comparisons[code] = {
                "previous": old,
                "current": now,
                "delta": delta,
                "signed_delta": f"{delta:+d}",
                "trend": "improving" if delta < 0 else "regressing" if delta > 0 else "flat",
                "lower_is_better": True,
            }

        efficiency_polarity = {
            "gpu_attempts": "lower",
            "refinement_passes": "lower",
            "pages_at_max_refinements": "lower",
            "pages_semantic_stalled": "lower",
            "avg_gpu_attempts_per_page": "lower",
            "gpu_attempts_per_semantic_pass": "lower",
            "semantic_yield_percent": "higher",
            "all_gate_yield_percent": "higher",
        }
        current_efficiency = current.get("generation_efficiency") or {}
        previous_efficiency = previous.get("generation_efficiency") or {}
        for name, polarity in efficiency_polarity.items():
            now = current_efficiency.get(name)
            old = previous_efficiency.get(name)
            if not isinstance(now, (int, float)) or not isinstance(old, (int, float)):
                continue
            delta = round(float(now) - float(old), 2)
            if delta == 0:
                trend_name = "flat"
            elif polarity == "higher":
                trend_name = "improving" if delta > 0 else "regressing"
            else:
                trend_name = "improving" if delta < 0 else "regressing"
            efficiency_comparisons[name] = {
                "previous": old,
                "current": now,
                "delta": delta,
                "signed_delta": f"{delta:+.2f}",
                "trend": trend_name,
                f"{polarity}_is_better": True,
            }

    appended = not history or history[-1].get("measurement_fingerprint") != current.get("measurement_fingerprint")
    if appended:
        history.append(current)
        history = history[-500:]
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in history),
            encoding="utf-8",
        )

    trend = {
        "schema_version": 1,
        "active_book_id": current.get("active_book_id"),
        "engine_commit": current.get("engine_commit"),
        "quality_contract_version": current.get("quality_contract_version"),
        "quality_contract_fingerprint": current.get("quality_contract_fingerprint"),
        "comparable_to_previous": comparable,
        "comparison_reason": reason,
        "history_appended": appended,
        "history_entries": len(history),
        "current_metrics": current.get("metrics") or {},
        "previous_metrics": (previous or {}).get("metrics") or {},
        "comparisons": comparisons,
        "defect_comparisons": defect_comparisons,
        "efficiency_comparisons": efficiency_comparisons,
        "current_generation_efficiency": current.get("generation_efficiency") or {},
        "previous_generation_efficiency": (previous or {}).get("generation_efficiency") or {},
        "current_defect_counts": current.get("defect_counts") or {},
        "current_historical_defect_counts": current.get("historical_defect_counts") or {},
        "previous_defect_counts": (previous or {}).get("defect_counts") or {},
        "replication": current.get("replication") or {},
    }
    trend_path.write_text(json.dumps(trend, indent=2) + "\n", encoding="utf-8")
    return appended


def publish_preview_snapshot(root: Path) -> str:
    engine_branch = output(root, "git", "branch", "--show-current")
    if not engine_branch:
        raise RuntimeError("Review publishing requires a checked-out engine branch")

    live_head = sync_live_decisions(root)
    append_quality_snapshot(root)
    source_dir = root / "review-previews"

    try:
        publish_head = publish_snapshot_once(
            root,
            source_dir,
            live_head,
            REVIEW_BRANCH,
        )
    except subprocess.CalledProcessError:
        print(
            "Review snapshot push failed once; refreshing live review state "
            "and retrying safely."
        )
        latest_live_head = sync_live_decisions(root)
        append_quality_snapshot(root)
        try:
            publish_head = publish_snapshot_once(
                root,
                source_dir,
                latest_live_head,
                REVIEW_BRANCH,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "Review snapshot publication failed twice; local snapshot "
                "remains intact for the next autopilot retry."
            ) from exc

    if publish_head == live_head:
        print("Review snapshot unchanged; leaving review-previews-live untouched.")
    else:
        print(
            "Review snapshot published from an isolated worktree; "
            "engine checkout and branch history were not mutated."
        )
    return publish_head
