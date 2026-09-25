from __future__ import annotations

import argparse
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
from vision_reviewer import VisionReviewError, review_image
from generation_runtime import model_filename, read_json
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
MONSTER_DIR = ROOT / "data" / "monsters"
WORKFLOW_DIR = ROOT / "art_pipeline" / "workflows" / "official"
OUTPUT_DIR = ROOT / "web" / "test-gallery"
STATE_FILE = ROOT / "data" / "test-gallery-state.json"
CANARY_PAGE_IDS = (
    "I-01", "I-04", "I-08", "I-10", "I-14", "I-16", "I-19", "I-20", "I-22",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def engine_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


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
            for page_id, selection in list(state["selections"].items()):
                if str((selection or {}).get("source") or "") == "assistant_review":
                    state["selections"].pop(page_id, None)
        state["copies_per_page"] = next_copies
        state["updated_at"] = utc_now()
        state.pop("completed_at", None)
        return state
    return {"schema_version": 3, "started_at": utc_now(), "updated_at": utc_now(), "copies_per_page": copies, "results": [], "selections": {}}


def generation_authority_stale(prior, current_fingerprint: str) -> bool:
    return bool(prior and str(prior.get("generation_fingerprint") or "") != str(current_fingerprint or ""))


def clear_selection_for_candidate(state: dict, page_id: str, candidate_no: int) -> bool:
    selected = (state.get("selections") or {}).get(str(page_id))
    if not selected or int(selected.get("candidate") or 0) != int(candidate_no):
        return False
    state["selections"].pop(str(page_id), None)
    return True


def should_skip_candidate(prior, rerun_failed: bool, force_rerun: bool = False, retry_max_refinements: bool = True) -> bool:
    if not prior:
        return False
    if force_rerun:
        return False
    retryable = {"failed", "technical_qa_failed", "vision_reviewer_failed", "assistant_rejected"}
    if retry_max_refinements:
        retryable.add("max_refinements_reached")
    return not (rerun_failed and prior.get("status") in retryable)


def load_pages():
    paths = active_book_paths(ROOT)
    tome = read_json(paths["manifest"])
    errors = validate_manifest(ROOT, tome, MONSTER_DIR)
    if errors:
        raise RuntimeError("Production manifest invalid: " + " | ".join(errors))
    return [resolve_page_spec(page, ROOT) for page in tome["pages"]]


def prepare(cli, config, page, seed: int, candidate_no: int, review_feedback=None):
    unet = model_filename(config, "diffusion_models")
    clip = model_filename(config, "text_encoders")
    vae = model_filename(config, "vae")
    path = WORKFLOW_DIR / f"test_{page['page_id'].lower()}_c{candidate_no:02d}.json"
    prepare_distilled_text_to_image(
        cli, config["templates"]["text_to_image"], path,
        prompt=build_prompt(page, review_feedback, candidate_no=candidate_no),
        seed=seed, model_filename=unet, clip_filename=clip, vae_filename=vae,
        width=768, height=1024,
    )
    verdict = envelope_data(cli.validate_workflow(path)) or {}
    if not verdict.get("valid"):
        raise RuntimeError("Prepared workflow failed validation: " + json.dumps(verdict))
    return path


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
    ready = sum(1 for row in rows if row["status"] == "ready_for_review")
    return {"ready": ready, "total": len(rows), "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a resumable multi-candidate test gallery for every Tome page")
    parser.add_argument("--copies", type=int, default=4)
    parser.add_argument("--start")
    parser.add_argument("--only")
    parser.add_argument("--candidate", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--rerun-failed", action="store_true")
    parser.add_argument("--canary", action="store_true")
    parser.add_argument("--canary-failed", action="store_true")
    args = parser.parse_args()
    if args.copies < 1:
        raise SystemExit("--copies must be at least 1")
    if args.canary and args.canary_failed:
        raise SystemExit("--canary and --canary-failed are mutually exclusive")
    if (args.canary or args.canary_failed) and (args.only or args.start or args.candidate is not None):
        raise SystemExit("--canary/--canary-failed cannot be combined with --only, --start, or --candidate")
    if args.candidate is not None and not args.only:
        raise SystemExit("--candidate requires --only")

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
    existing = {(str(item.get("page_id")), int(item.get("candidate") or 0)): item for item in state.get("results", [])}
    sequence = len(state.get("results", []))

    for page in pages:
        candidate_numbers = [args.candidate] if args.candidate is not None else range(1, args.copies + 1)
        for candidate_no in candidate_numbers:
            prior = existing.get((page["page_id"], candidate_no))
            retry_failed = args.rerun_failed or args.canary_failed
            current_fingerprint = page_generation_fingerprint(page, ROOT)
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
            stale_generation_authority = generation_authority_stale(prior, current_fingerprint)
            if should_skip_candidate(
                prior,
                retry_failed,
                force_rerun=args.canary or (args.canary_failed and stale_generation_authority),
                retry_max_refinements=not args.canary_failed,
            ):
                print(json.dumps({"page_id": page["page_id"], "candidate": candidate_no, "status": "skipped_existing"}))
                continue
            if prior:
                clear_selection_for_candidate(state, page["page_id"], candidate_no)
                state["results"].remove(prior)
            sequence += 1
            seed = (args.seed + sequence) if args.seed is not None else random.randint(1, 2**63 - 1)
            record = {
                "page_id": page["page_id"],
                "monster_name": page["monster_name"],
                "candidate": candidate_no,
                "seed": seed,
                "engine_commit": engine_commit(),
                "generation_fingerprint": current_fingerprint,
                "review_fingerprint": page_review_fingerprint(page, ROOT),
                "started_at": utc_now(),
            }
            try:
                review_feedback = None
                if prior and prior.get("status") == "technical_qa_failed":
                    review_feedback = margin_recovery_feedback(prior) if is_safe_margin_failure(prior) else generic_qa_recovery_feedback(prior)
                elif prior and prior.get("status") == "assistant_rejected":
                    notes = str(((prior.get("assistant_review") or {}).get("notes")) or "").strip()
                    review_feedback = {"text": notes or "Previous candidate was rejected during visual review.", "routing_recommendation": "regenerate"}
                workflow = prepare(cli, config, page, seed, candidate_no, review_feedback)
                relative = execute_candidate(cli, client, workflow, page["page_id"], candidate_no, inspect_candidate)
                source = ROOT / "web" / relative
                destination = OUTPUT_DIR / f"{page['page_id']}-C{candidate_no:02d}.png"
                destination.write_bytes(source.read_bytes())
                visual_verdict = review_image(page, destination, config)
                record.update({
                    "status": "ready_for_review" if visual_verdict.get("pass") else "max_refinements_reached",
                    "image_path": destination.relative_to(ROOT / "web").as_posix(),
                    "visual_review": visual_verdict,
                })
            except TechnicalQAError as exc:
                streak = next_qa_fail_streak(prior, current_fingerprint)
                record.update({
                    "status": "technical_qa_stalled" if streak >= QA_STALL_LIMIT else "technical_qa_failed",
                    "error": str(exc),
                    "qa_fail_streak": streak,
                })
            except VisionReviewError as exc:
                record.update({"status": "vision_reviewer_failed", "error": str(exc)})
                state["results"].append(record)
                write_state(state)
                print(json.dumps(record))
                raise SystemExit("FATAL: semantic vision reviewer failed")
            except Exception as exc:
                record.update({"status": "failed", "error": str(exc)})
            record["finished_at"] = utc_now()
            state["results"].append(record)
            existing[(page["page_id"], candidate_no)] = record
            state["updated_at"] = utc_now()
            write_state(state)
            print(json.dumps(record))

    state["completed_at"] = utc_now()
    write_state(state)
    print(f"Test gallery complete: {len(state['results'])} attempts")
    if args.canary or args.canary_failed:
        summary = canary_summary(state)
        print(f"CANARY SUMMARY: {summary['ready']}/{summary['total']} ready_for_review")
        for row in summary["rows"]:
            defects = "; ".join(row["defects"]) if row["defects"] else "none"
            print(f"  {row['page_id']}: {row['status']} stage={row['stage'] or 'n/a'} score={row['score']} defects={defects}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
