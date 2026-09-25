from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from candidate_runner import TechnicalQAError, execute_candidate
from comfy_cli_runner import ComfyCli
from comfy_client import ComfyClient
from flux2_klein_profile import envelope_data, prepare_distilled_text_to_image
from image_edit_profile import prepare_distilled_image_edit
from edit_prompt import build_edit_prompt
from vision_reviewer import VisionReviewError, review_image, review_notes
from generation_runtime import model_filename, read_json
from generation_lint import assert_generation_ready
from generation_fingerprint import page_generation_fingerprint, page_review_fingerprint
from manifest_validation import validate_manifest
from page_contract import resolve_page_spec
from prompt_builder import build_prompt
from qa import inspect_candidate
from qa_recovery import (
    QA_STALL_LIMIT,
    generic_qa_recovery_feedback,
    is_safe_margin_failure,
    margin_recovery_feedback,
    next_qa_fail_streak,
    prior_error_text,
    qa_fail_streak,
    same_fingerprint_qa_stall,
)
from studio_config import active_book_paths

CONFIG_FILE = ROOT / "config" / "local_ai_stack.json"
QUALITY_SCORECARD_FILE = ROOT / "config" / "quality_scorecard.json"
MONSTER_DIR = ROOT / "data" / "monsters"
WORKFLOW_DIR = ROOT / "art_pipeline" / "workflows" / "official"
OUTPUT_DIR = ROOT / "web" / "test-gallery"
STATE_FILE = ROOT / "data" / "test-gallery-state.json"
AUTHORITY_FILES = [
    ROOT / "config" / "universal_monster_contract.json",
    ROOT / "config" / "universal_environment_contract.json",
    ROOT / "config" / "universal_page_contract.json",
    ROOT / "config" / "coloring_page_standard.json",
]

def configured_canary_page_ids() -> tuple[str, ...]:
    config = read_json(QUALITY_SCORECARD_FILE)
    page_ids = tuple(
        str(page_id).strip()
        for page_id in config.get("canary_page_ids") or []
        if str(page_id).strip()
    )
    if not page_ids:
        raise RuntimeError("quality scorecard must declare canary_page_ids")
    if len(page_ids) != len(set(page_ids)):
        raise RuntimeError("quality scorecard canary_page_ids must be unique")
    return page_ids


CANARY_PAGE_IDS = configured_canary_page_ids()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def engine_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def reload_authority() -> dict:
    # Intentionally re-read every authority before EVERY candidate, including
    # repeats of the same monster. This lets an operator stop, fix drift, and
    # resume with the next image using the new rules.
    return {p.name: read_json(p) for p in AUTHORITY_FILES}


def write_state(payload: dict) -> None:
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def load_or_init_state(copies: int, reset: bool = False) -> dict:
    if STATE_FILE.exists() and not reset:
        state = read_json(STATE_FILE)
        state.setdefault("results", [])
        state.setdefault("selections", {})
        previous_copies = int(state.get("copies_per_page") or 0)
        next_copies = max(previous_copies, copies)
        if previous_copies <= 1 and next_copies > 1:
            # Canary approval may auto-select its only candidate. Once the same
            # state expands into a multi-candidate production gallery, final
            # choice must be explicit across the candidate set. Keep the exact
            # image approval on the result record, but clear only the automatic
            # one-candidate selection.
            for page_id, selection in list(state["selections"].items()):
                if str((selection or {}).get("source") or "") == "assistant_review":
                    state["selections"].pop(page_id, None)
        state["copies_per_page"] = next_copies
        state["updated_at"] = utc_now()
        state.pop("completed_at", None)
        return state
    return {
        "schema_version": 3,
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "copies_per_page": copies,
        "results": [],
        "selections": {},
    }


def generation_authority_stale(prior: dict | None, current_fingerprint: str) -> bool:
    return bool(
        prior
        and str(prior.get("generation_fingerprint") or "")
        != str(current_fingerprint or "")
    )


def review_authority_stale(prior: dict | None, current_fingerprint: str) -> bool:
    return bool(
        prior
        and str(prior.get("review_fingerprint") or "")
        != str(current_fingerprint or "")
    )


def same_fingerprint_semantic_stall(
    prior: dict | None,
    generation_fingerprint: str,
    review_fingerprint: str,
) -> bool:
    """Stop repeating exhausted semantic work until relevant authority changes."""
    if not prior:
        return False
    if str(prior.get("status") or "") not in {
        "max_refinements_reached",
        "semantic_stalled",
    }:
        return False
    if str(prior.get("generation_fingerprint") or "") != str(generation_fingerprint or ""):
        return False
    if str(prior.get("review_fingerprint") or "") != str(review_fingerprint or ""):
        return False
    verdict = prior.get("visual_review") or {}
    return bool(verdict) and not bool(verdict.get("pass"))


def existing_candidate_path(item: dict) -> Path | None:
    image_path = str(item.get("image_path") or "").strip()
    if not image_path:
        return None
    path = ROOT / "web" / image_path
    return path if path.exists() and path.is_file() else None


def clear_selection_for_candidate(state: dict, page_id: str, candidate_no: int) -> bool:
    selected = (state.get("selections") or {}).get(str(page_id))
    if not selected:
        return False
    if int(selected.get("candidate") or 0) != int(candidate_no):
        return False
    state["selections"].pop(str(page_id), None)
    return True


def current_review_id(item: dict | None) -> str | None:
    if not item:
        return None
    path = existing_candidate_path(item)
    if path is None:
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return (
        f"{item.get('page_id')}-C{int(item.get('candidate') or 0):02d}-"
        f"H{digest[:16]}"
    )


def exact_assistant_approval_is_current(
    prior: dict | None,
    current_generation_fingerprint: str,
) -> bool:
    if not prior:
        return False
    if generation_authority_stale(prior, current_generation_fingerprint):
        return False
    assistant = prior.get("assistant_review") or {}
    if str(assistant.get("decision") or "").lower() not in {"approve", "select"}:
        return False
    recorded = str(assistant.get("review_id") or "")
    return bool(recorded and recorded == current_review_id(prior))


def assistant_repair_plan(prior: dict | None) -> tuple[Path | None, dict | None]:
    if not prior or str(prior.get("status") or "") != "assistant_rejected":
        return None, None
    assistant_review = prior.get("assistant_review") or {}
    stage = str(assistant_review.get("stage") or "").strip().lower()
    source = existing_candidate_path(prior)
    if stage not in {"environment", "action", "quality"} or source is None:
        return None, None
    notes = str(assistant_review.get("notes") or "").strip()
    return source, {
        "pass": False,
        "score": 0,
        "stage": stage,
        "defects": [
            notes
            or "Exact-image review rejected this stage and requires targeted repair."
        ],
        "preserve": [],
    }


def should_skip_candidate(
    prior: dict | None,
    rerun_failed: bool,
    force_rerun: bool = False,
    retry_max_refinements: bool = True,
) -> bool:
    if not prior:
        return False
    if force_rerun:
        return False
    retryable = {
        "failed",
        "technical_qa_failed",
        "vision_reviewer_failed",
        "assistant_rejected",
    }
    if retry_max_refinements:
        retryable.add("max_refinements_reached")
    return not (rerun_failed and prior.get("status") in retryable)


def load_pages() -> list[dict]:
    paths = active_book_paths(ROOT)
    tome = read_json(paths["manifest"])
    errors = validate_manifest(ROOT, tome, MONSTER_DIR)
    if errors:
        raise RuntimeError("Production manifest invalid: " + " | ".join(errors))
    return [resolve_page_spec(page, ROOT) for page in tome["pages"]]


def prepare(cli, config, page, seed: int, candidate_no: int, review_feedback: dict | None = None) -> Path:
    unet = model_filename(config, "diffusion_models")
    clip = model_filename(config, "text_encoders")
    vae = model_filename(config, "vae")
    path = WORKFLOW_DIR / f"test_{page['page_id'].lower()}_c{candidate_no:02d}.json"
    prompt = build_prompt(page, review_feedback, candidate_no=candidate_no)
    assert_generation_ready(page, prompt, ROOT)
    meta = prepare_distilled_text_to_image(
        cli,
        config["templates"]["text_to_image"],
        path,
        prompt=prompt,
        seed=seed,
        model_filename=unet,
        clip_filename=clip,
        vae_filename=vae,
        width=768,
        height=1024,
    )
    verdict = envelope_data(cli.validate_workflow(path)) or {}
    if not verdict.get("valid"):
        raise RuntimeError("Prepared workflow failed validation: " + json.dumps(verdict))
    return path


def prepare_edit(cli, client, config, page, seed: int, candidate_no: int, source: Path, verdict: dict, pass_no: int) -> Path:
    # Reload written authority before EVERY repair pass. The source image is never authority.
    reload_authority()
    unet = model_filename(config, "diffusion_models")
    clip = model_filename(config, "text_encoders")
    vae = model_filename(config, "vae")
    uploaded = client.upload_image(source, subfolder="blackink-refinements")
    path = WORKFLOW_DIR / f"test_{page['page_id'].lower()}_c{candidate_no:02d}_r{pass_no:02d}.json"
    prepare_distilled_image_edit(
        cli, config["templates"]["modify"] if "modify" in config["templates"] else config["templates"]["image_edit"], path,
        prompt=build_edit_prompt(page, review_notes(verdict), candidate_no=candidate_no),
        seed=seed, input_image=uploaded["load_image_name"],
        model_filename=unet, clip_filename=clip, vae_filename=vae,
    )
    checked = envelope_data(cli.validate_workflow(path)) or {}
    if not checked.get("valid"):
        raise RuntimeError("Prepared refinement workflow failed validation: " + json.dumps(checked))
    return path


def reuse_existing_image_after_reviewer_recheck(verdict: dict) -> bool:
    """Reuse current pixels after reviewer-only changes unless identity is wrong."""
    if verdict.get("pass"):
        return False
    stage = str(verdict.get("stage") or "").strip().lower()
    return stage in {"environment", "scene", "action", "quality"}


def verdict_rank(verdict: dict) -> tuple:
    stage = str(verdict.get("stage") or "").strip().lower()
    # Passed work always wins. Among failures, gate progress outranks numeric
    # score: environment proves identity passed; action proves identity +
    # environment passed; quality proves all structural gates passed. Never
    # restore an older identity-failing image
    # merely because its local-model score is numerically higher.
    stage_progress = {
        "identity": 1,
        "environment": 2,
        "scene": 2,
        "action": 3,
        "quality": 4,
    }.get(stage, 0)
    return (
        1 if verdict.get("pass") else 0,
        stage_progress,
        int(verdict.get("score") or 0),
        -len(verdict.get("defects") or []),
    )


def refine_candidate(cli, client, config, page, candidate_no: int, seed: int, initial: Path) -> tuple[Path, dict, list]:
    max_refinements = int((config.get("vision_reviewer") or {}).get("max_refinement_passes", 4))
    current = initial
    reload_authority()
    verdict = review_image(page, current, config)
    history = [{"pass": 0, "image": str(current), "review": verdict}]
    best, best_verdict = current, verdict
    for pass_no in range(1, max_refinements + 1):
        if verdict.get("pass"):
            break
        stage = str(verdict.get("stage") or "").strip().lower()
        trailing_same_stage = 0
        for step in reversed(history):
            review = step.get("review") or {}
            if review.get("pass"):
                break
            if str(review.get("stage") or "").strip().lower() != stage:
                break
            trailing_same_stage += 1

        identity_stagnation = stage == "identity" and trailing_same_stage >= 2
        structural_stagnation = (
            stage in {"environment", "scene", "action"}
            and trailing_same_stage >= 2
        )
        if stage == "identity" or structural_stagnation:
            # Wrong anatomy should never be anchored to a bad source image.
            # Likewise, if an environment/action edit failed to advance the
            # same gate once, stop spending passes polishing the same broken
            # composition and rebuild fresh from written authority + defects.
            feedback = review_notes(verdict)
            feedback["routing_recommendation"] = "regenerate"
            feedback["stagnation_escalation"] = bool(
                structural_stagnation or identity_stagnation
            )
            if structural_stagnation or identity_stagnation:
                feedback["composition_escape_offset"] = pass_no
            workflow = prepare(
                cli,
                config,
                page,
                seed + pass_no,
                candidate_no,
                feedback,
            )
        else:
            # First environment/action repair and all quality repairs are
            # cumulative image edits so successful anatomy/scene work survives.
            workflow = prepare_edit(
                cli,
                client,
                config,
                page,
                seed + pass_no,
                candidate_no,
                current,
                verdict,
                pass_no,
            )
        relative = execute_candidate(cli, client, workflow, f"{page['page_id']}-C{candidate_no:02d}-R{pass_no:02d}", pass_no, inspect_candidate)
        current = ROOT / "web" / relative
        reload_authority()
        verdict = review_image(page, current, config)
        history.append({"pass": pass_no, "image": str(current), "review": verdict})
        if verdict_rank(verdict) > verdict_rank(best_verdict):
            best, best_verdict = current, verdict
    return best, best_verdict, history


def canary_summary(state: dict) -> dict:
    wanted = set(CANARY_PAGE_IDS)
    latest = {
        (str(item.get("page_id")), int(item.get("candidate") or 0)): item
        for item in state.get("results", [])
        if str(item.get("page_id")) in wanted and int(item.get("candidate") or 0) == 1
    }
    rows = []
    for page_id in CANARY_PAGE_IDS:
        item = latest.get((page_id, 1)) or {}
        rows.append({
            "page_id": page_id,
            "status": str(item.get("status") or "missing"),
            "score": int(((item.get("visual_review") or {}).get("score")) or 0),
            "stage": str(((item.get("visual_review") or {}).get("stage")) or ""),
            "defects": list(((item.get("visual_review") or {}).get("defects")) or []),
        })
    reviewable = sum(
        1 for row in rows
        if row["status"] == "awaiting_exact_image_review"
    )
    return {"ready": reviewable, "total": len(rows), "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a resumable multi-candidate test gallery for every Tome page")
    parser.add_argument("--copies", type=int, default=4, help="Independent candidates per monster/page")
    parser.add_argument("--start", help="Optional page id to start/resume from")
    parser.add_argument("--only", help="Optional page id to test repeatedly")
    parser.add_argument("--candidate", type=int, help="Optional candidate number to run (requires --only)")
    parser.add_argument("--seed", type=int, help="Base seed for reproducible testing")
    parser.add_argument("--reset", action="store_true", help="Start a fresh gallery and discard prior test state")
    parser.add_argument("--rerun-failed", action="store_true", help="Retry candidates whose prior status was failed")
    parser.add_argument("--canary", action="store_true", help="Run the configured engine canary set and force those selected candidates to regenerate")
    parser.add_argument("--canary-failed", action="store_true", help="Run the configured canary set but retry only missing, failed, or assistant-rejected candidates")
    args = parser.parse_args()
    if args.copies < 1:
        raise SystemExit("--copies must be at least 1")
    if args.canary and args.canary_failed:
        raise SystemExit("--canary and --canary-failed are mutually exclusive")
    if (args.canary or args.canary_failed) and (args.only or args.start or args.candidate is not None):
        raise SystemExit("--canary/--canary-failed cannot be combined with --only, --start, or --candidate")
    if args.candidate is not None and not args.only:
        raise SystemExit("--candidate requires --only")
    if args.candidate is not None and args.candidate < 1:
        raise SystemExit("--candidate must be at least 1")

    config = read_json(CONFIG_FILE)
    client = ComfyClient(config["comfy_url"])
    client.health()
    cli = ComfyCli()
    pages = load_pages()
    if args.canary or args.canary_failed:
        wanted = set(CANARY_PAGE_IDS)
        pages = [page for page in pages if page["page_id"] in wanted]
        if [page["page_id"] for page in pages] != list(CANARY_PAGE_IDS):
            raise SystemExit("Canary page set is incomplete or out of order")
    elif args.only:
        pages = [p for p in pages if p["page_id"] == args.only]
        if not pages:
            raise SystemExit(f"Unknown page id: {args.only}")
    elif args.start:
        ids = [p["page_id"] for p in pages]
        if args.start not in ids:
            raise SystemExit(f"Unknown start page id: {args.start}")
        pages = pages[ids.index(args.start):]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_or_init_state(args.copies, args.reset)
    write_state(state)

    existing = {
        (str(item.get("page_id")), int(item.get("candidate") or 0)): item
        for item in state.get("results", [])
    }

    sequence = len(state.get("results", []))
    for page in pages:
        candidate_numbers = [args.candidate] if args.candidate is not None else range(1, args.copies + 1)
        for candidate_no in candidate_numbers:
            prior = existing.get((page["page_id"], candidate_no))
            retry_failed = args.rerun_failed or args.canary_failed
            current_fingerprint = page_generation_fingerprint(page, ROOT)
            current_review_fingerprint = page_review_fingerprint(page, ROOT)
            if (
                not args.canary
                and same_fingerprint_semantic_stall(
                    prior,
                    current_fingerprint,
                    current_review_fingerprint,
                )
            ):
                if prior and str(prior.get("status") or "") != "semantic_stalled":
                    prior["status"] = "semantic_stalled"
                    prior["semantic_stall"] = {
                        "generation_fingerprint": current_fingerprint,
                        "review_fingerprint": current_review_fingerprint,
                        "stage": str((prior.get("visual_review") or {}).get("stage") or ""),
                        "defects": list((prior.get("visual_review") or {}).get("defects") or []),
                        "at": utc_now(),
                    }
                    state["updated_at"] = utc_now()
                    write_state(state)
                print(json.dumps({
                    "page_id": page["page_id"],
                    "candidate": candidate_no,
                    "status": "skipped_semantic_stalled",
                    "review_stage": str((prior.get("visual_review") or {}).get("stage") or "") if prior else "",
                    "defects": list((prior.get("visual_review") or {}).get("defects") or []) if prior else [],
                }))
                continue
            if same_fingerprint_qa_stall(prior, current_fingerprint):
                if prior and str(prior.get("status") or "") != "technical_qa_stalled":
                    prior["status"] = "technical_qa_stalled"
                    state["updated_at"] = utc_now()
                    write_state(state)
                print(json.dumps({
                    "page_id": page["page_id"],
                    "candidate": candidate_no,
                    "status": "skipped_qa_stalled",
                    "qa_fail_streak": qa_fail_streak(prior),
                    "error": prior_error_text(prior),
                }))
                continue
            stale_generation_authority = generation_authority_stale(
                prior,
                current_fingerprint,
            )
            stale_review_authority = review_authority_stale(
                prior,
                current_review_fingerprint,
            )
            current_exact_approval = exact_assistant_approval_is_current(
                prior,
                current_fingerprint,
            )
            if current_exact_approval:
                print(json.dumps({
                    "page_id": page["page_id"],
                    "candidate": candidate_no,
                    "status": "skipped_exact_image_approved",
                }))
                continue

            reviewer_recheck_failed = False
            reviewer_recheck_feedback = None
            reviewer_recheck_source = None
            if (
                prior
                and not stale_generation_authority
                and stale_review_authority
                and str(prior.get("status") or "") in {"ready_for_review", "max_refinements_reached"}
            ):
                prior_image = existing_candidate_path(prior)
                if prior_image is not None:
                    reload_authority()
                    try:
                        refreshed_review = review_image(page, prior_image, config)
                    except VisionReviewError as exc:
                        prior["status"] = "awaiting_exact_image_review"
                        prior["advisory_review_status"] = "unavailable"
                        prior["advisory_review_error"] = str(exc)
                        prior["review_fingerprint"] = current_review_fingerprint
                        prior["review_checked_at"] = utc_now()
                        state["updated_at"] = utc_now()
                        write_state(state)
                        print(json.dumps({
                            "page_id": page["page_id"],
                            "candidate": candidate_no,
                            "status": "advisory_review_unavailable",
                            "error": str(exc),
                        }))
                    prior["visual_review"] = refreshed_review
                    prior["review_fingerprint"] = current_review_fingerprint
                    prior["review_checked_at"] = utc_now()
                    prior["engine_commit"] = engine_commit()
                    prior["status"] = "awaiting_exact_image_review"
                    prior["advisory_review_status"] = (
                        "pass" if refreshed_review.get("pass") else "needs_work"
                    )
                    if not refreshed_review.get("pass"):
                        reviewer_recheck_failed = True
                        if reuse_existing_image_after_reviewer_recheck(refreshed_review):
                            reviewer_recheck_source = prior_image
                        reviewer_recheck_feedback = review_notes(refreshed_review)
                        reviewer_recheck_feedback["routing_recommendation"] = "regenerate"
                        clear_selection_for_candidate(
                            state,
                            page["page_id"],
                            candidate_no,
                        )
                    prior.pop("error", None)
                    state["updated_at"] = utc_now()
                    write_state(state)
                    print(json.dumps({
                        "page_id": page["page_id"],
                        "candidate": candidate_no,
                        "status": "review_rechecked",
                        "review_stage": refreshed_review.get("stage"),
                        "review_pass": bool(refreshed_review.get("pass")),
                        "score": int(refreshed_review.get("score") or 0),
                    }))

            assistant_repair_source, assistant_repair_verdict = assistant_repair_plan(prior)

            if should_skip_candidate(
                prior,
                retry_failed,
                force_rerun=(
                    args.canary
                    or (args.canary_failed and stale_generation_authority)
                ),
                retry_max_refinements=(
                    not args.canary_failed
                    or reviewer_recheck_failed
                ),
            ):
                print(json.dumps({"page_id": page["page_id"], "candidate": candidate_no, "status": "skipped_existing"}))
                continue
            if prior:
                clear_selection_for_candidate(
                    state,
                    page["page_id"],
                    candidate_no,
                )
                state["results"].remove(prior)
            sequence += 1
            reload_authority()
            seed = (args.seed + sequence) if args.seed is not None else random.randint(1, 2**63 - 1)
            record = {
                "page_id": page["page_id"],
                "monster_name": page["monster_name"],
                "candidate": candidate_no,
                "seed": seed,
                "engine_commit": engine_commit(),
                "generation_fingerprint": current_fingerprint,
                "review_fingerprint": current_review_fingerprint,
                "started_at": utc_now(),
            }
            try:
                review_feedback = reviewer_recheck_feedback
                if prior and prior.get("status") == "technical_qa_failed":
                    review_feedback = (
                        margin_recovery_feedback(prior)
                        if is_safe_margin_failure(prior)
                        else generic_qa_recovery_feedback(prior)
                    )
                if prior and prior.get("status") == "assistant_rejected":
                    assistant_review = prior.get("assistant_review") or {}
                    notes = (assistant_review.get("notes") or "").strip()
                    stage = str(assistant_review.get("stage") or "").strip().lower()
                    review_feedback = {
                        "text": notes or "Previous candidate was rejected during visual review. Rebuild the failed composition.",
                        "routing_recommendation": "regenerate",
                    }
                    if stage in {"identity", "environment", "action", "quality"}:
                        review_feedback["stage"] = stage
                if assistant_repair_source is not None:
                    # Exact-image environment/action/quality rejection keeps the
                    # successful creature pixels and performs one targeted edit
                    # before returning to the normal staged reviewer loop.
                    workflow = prepare_edit(
                        cli,
                        client,
                        config,
                        page,
                        seed + 1,
                        candidate_no,
                        assistant_repair_source,
                        assistant_repair_verdict,
                        1,
                    )
                    relative = execute_candidate(
                        cli,
                        client,
                        workflow,
                        f"{page['page_id']}-C{candidate_no:02d}-A01",
                        1,
                        inspect_candidate,
                    )
                    source = ROOT / "web" / relative
                elif reviewer_recheck_source is not None:
                    # Reuse the current exact image as the refinement source.
                    # refine_candidate will route identity failures to fresh
                    # text generation, while environment/action/quality
                    # failures preserve good pixels through image editing.
                    source = reviewer_recheck_source
                else:
                    workflow = prepare(cli, config, page, seed, candidate_no, review_feedback)
                    relative = execute_candidate(
                        cli, client, workflow, page["page_id"], candidate_no, inspect_candidate
                    )
                    source = ROOT / "web" / relative
                best, visual_verdict, pass_history = refine_candidate(
                    cli, client, config, page, candidate_no, seed, source
                )
                destination = OUTPUT_DIR / f"{page['page_id']}-C{candidate_no:02d}.png"
                destination.write_bytes(best.read_bytes())
                record.update({
                    "status": "awaiting_exact_image_review",
                    "image_path": destination.relative_to(ROOT / "web").as_posix(),
                    "visual_review": visual_verdict,
                    "advisory_review_status": (
                        "pass" if visual_verdict.get("pass") else "needs_work"
                    ),
                    "pass_history": pass_history,
                })
            except VisionReviewError as exc:
                destination = OUTPUT_DIR / f"{page['page_id']}-C{candidate_no:02d}.png"
                if "source" in locals() and Path(source).exists():
                    destination.write_bytes(Path(source).read_bytes())
                    record.update({
                        "status": "awaiting_exact_image_review",
                        "image_path": destination.relative_to(ROOT / "web").as_posix(),
                        "advisory_review_status": "unavailable",
                        "advisory_review_error": str(exc),
                        "pass_history": [],
                    })
                else:
                    record.update({
                        "status": "failed",
                        "error": f"Advisory reviewer failed before a technical candidate was preserved: {exc}",
                    })
            except TechnicalQAError as exc:
                streak = next_qa_fail_streak(prior, current_fingerprint)
                record.update({
                    "status": (
                        "technical_qa_stalled"
                        if streak >= QA_STALL_LIMIT
                        else "technical_qa_failed"
                    ),
                    "error": str(exc),
                    "qa_fail_streak": streak,
                })
            except Exception as exc:
                record.update({"status": "failed", "error": str(exc)})
            record["finished_at"] = utc_now()
            state["results"].append(record)
            existing[(page["page_id"], candidate_no)] = record
            state["updated_at"] = utc_now()
            write_state(state)
            print(json.dumps(record))

    state["completed_at"] = utc_now()
    state["updated_at"] = utc_now()
    write_state(state)
    print(f"Test gallery complete: {len(state['results'])} attempts")
    if args.canary or args.canary_failed:
        summary = canary_summary(state)
        print(f"CANARY SUMMARY: {summary['ready']}/{summary['total']} awaiting_exact_image_review")
        for row in summary["rows"]:
            defects = "; ".join(row["defects"]) if row["defects"] else "none"
            print(
                f"  {row['page_id']}: {row['status']} stage={row['stage'] or 'n/a'} "
                f"score={row['score']} defects={defects}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
