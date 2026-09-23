from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from candidate_runner import TechnicalQAError, execute_candidate
from comfy_cli_runner import ComfyCli
from comfy_client import ComfyClient
from flux2_klein_profile import envelope_data, prepare_distilled_text_to_image
from generation_runtime import model_filename, read_json
from manifest_validation import validate_manifest
from page_contract import resolve_page_spec
from prompt_builder import build_prompt
from qa import inspect_candidate
from studio_config import active_book_paths

CONFIG_FILE = ROOT / "config" / "local_ai_stack.json"
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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        state["copies_per_page"] = max(int(state.get("copies_per_page") or 0), copies)
        state["updated_at"] = utc_now()
        state.pop("completed_at", None)
        return state
    return {
        "schema_version": 2,
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "copies_per_page": copies,
        "results": [],
        "selections": {},
    }


def should_skip_candidate(prior: dict | None, rerun_failed: bool) -> bool:
    if not prior:
        return False
    return not (rerun_failed and prior.get("status") in {"failed", "technical_qa_failed"})


def load_pages() -> list[dict]:
    paths = active_book_paths(ROOT)
    tome = read_json(paths["manifest"])
    errors = validate_manifest(ROOT, tome, MONSTER_DIR)
    if errors:
        raise RuntimeError("Production manifest invalid: " + " | ".join(errors))
    return [resolve_page_spec(page, ROOT) for page in tome["pages"]]


def prepare(cli, config, page, seed: int, candidate_no: int) -> Path:
    unet = model_filename(config, "diffusion_models")
    clip = model_filename(config, "text_encoders")
    vae = model_filename(config, "vae")
    path = WORKFLOW_DIR / f"test_{page['page_id'].lower()}_c{candidate_no:02d}.json"
    meta = prepare_distilled_text_to_image(
        cli,
        config["templates"]["text_to_image"],
        path,
        prompt=build_prompt(page),
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a resumable multi-candidate test gallery for every Tome page")
    parser.add_argument("--copies", type=int, default=4, help="Independent candidates per monster/page")
    parser.add_argument("--start", help="Optional page id to start/resume from, e.g. I-24")
    parser.add_argument("--only", help="Optional page id to test repeatedly")
    parser.add_argument("--seed", type=int, help="Base seed for reproducible testing")
    parser.add_argument("--reset", action="store_true", help="Start a fresh gallery and discard prior test state")
    parser.add_argument("--rerun-failed", action="store_true", help="Retry candidates whose prior status was failed")
    args = parser.parse_args()
    if args.copies < 1:
        raise SystemExit("--copies must be at least 1")

    config = read_json(CONFIG_FILE)
    client = ComfyClient(config["comfy_url"])
    client.health()
    cli = ComfyCli()
    pages = load_pages()
    if args.only:
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
        for candidate_no in range(1, args.copies + 1):
            prior = existing.get((page["page_id"], candidate_no))
            if should_skip_candidate(prior, args.rerun_failed):
                print(json.dumps({"page_id": page["page_id"], "candidate": candidate_no, "status": "skipped_existing"}))
                continue
            if prior:
                state["results"].remove(prior)
            sequence += 1
            reload_authority()
            seed = (args.seed + sequence) if args.seed is not None else random.randint(1, 2**63 - 1)
            record = {
                "page_id": page["page_id"],
                "monster_name": page["monster_name"],
                "candidate": candidate_no,
                "seed": seed,
                "started_at": utc_now(),
            }
            try:
                workflow = prepare(cli, config, page, seed, candidate_no)
                relative = execute_candidate(
                    cli, client, workflow, page["page_id"], candidate_no, inspect_candidate
                )
                source = ROOT / "web" / relative
                destination = OUTPUT_DIR / f"{page['page_id']}-C{candidate_no:02d}.png"
                destination.write_bytes(source.read_bytes())
                record.update({"status": "ready_for_review", "image_path": destination.relative_to(ROOT / "web").as_posix()})
            except TechnicalQAError as exc:
                record.update({"status": "technical_qa_failed", "error": str(exc)})
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
