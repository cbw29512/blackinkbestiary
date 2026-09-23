from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from comfy_cli_runner import ComfyCli, ComfyCliError
from comfy_client import ComfyClient
from prompt_builder import build_prompt
from qa import inspect_candidate
from smoke_test_support import (
    ensure_studio,
    find_prompt_id,
    load_current,
    model_filename,
    post_json,
    prepare_i01_workflow,
    read_json,
)

CONFIG_FILE = ROOT / "config" / "local_ai_stack.json"
WORKFLOW_DIR = ROOT / "art_pipeline" / "workflows" / "official"
CANDIDATE_DIR = ROOT / "web" / "candidates"
STUDIO_URL = "http://127.0.0.1:8765"


def _download_best_candidate(client, images, page_state):
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    attempt = int(page_state.get("attempt", 0)) + 1
    accepted = None
    reports = []
    for index, image in enumerate(images, start=1):
        path = CANDIDATE_DIR / f"I-01-smoke-A{attempt:03d}-{index}.png"
        client.download_image(image, path)
        report = inspect_candidate(path)
        reports.append(report)
        if accepted is None and report.get("pass"):
            accepted = path
    return accepted, reports, attempt


def main() -> int:
    config = read_json(CONFIG_FILE)
    page, page_state = load_current(ROOT)
    if page["page_id"] != "I-01":
        print(
            "Smoke test is intentionally locked to I-01; "
            f"current page is {page['page_id']}."
        )
        return 2

    print("Black-Ink Bestiary — I-01 Local Smoke Test")
    print("==========================================")
    print(f"Page: {page['page_id']} — {page['monster_name']}")

    cli = ComfyCli()
    client = ComfyClient(config["comfy_url"])
    try:
        client.health()
    except Exception as exc:
        print(f"Local ComfyUI is not ready: {exc}")
        print("Run INSTALL_BLACKINK_AI.bat first.")
        return 3

    seed = random.randint(1, 2**63 - 1)
    prompt = build_prompt(page, page_state.get("review_notes"))
    try:
        workflow_path, prepared = prepare_i01_workflow(
            cli, config, prompt, seed, WORKFLOW_DIR
        )
    except (ComfyCliError, RuntimeError) as exc:
        print(f"Could not prepare the distilled FLUX workflow: {exc}")
        return 4

    print(f"Template: {config['templates']['text_to_image']}")
    print(f"Distilled branch: {prepared['selected_root']}")
    print(f"Model: {model_filename(config, 'diffusion_models')}")
    print(f"Seed: {seed}")
    print("Generating one calibration candidate...")

    try:
        result = cli.run_workflow(workflow_path, timeout=600)
    except ComfyCliError as exc:
        print(exc)
        print(
            "\nIf the error mentions DynamicVRAM/VBAR/CUDA OOM on the RTX 5060 Ti, "
            "run RESTART_AI_SAFE_MODE.bat and retry."
        )
        return 4

    prompt_id = find_prompt_id(result)
    if not prompt_id:
        print("Generation returned no prompt_id.")
        print(json.dumps(result, indent=2))
        return 5

    history_entry = client.history(prompt_id).get(prompt_id)
    if not history_entry:
        print(f"ComfyUI has no completed history entry for {prompt_id}.")
        return 6
    images = client.output_images(history_entry)
    if not images:
        print("Generation completed but no SaveImage output was found.")
        return 7

    accepted, reports, attempt = _download_best_candidate(
        client, images, page_state
    )
    print("\nQA:")
    for report in reports:
        status = "PASS" if report.get("pass") else "FAIL"
        print(f"- {Path(report['path']).name}: {status} {report.get('reasons', [])}")
    if accepted is None:
        print("No smoke-test output passed basic production QA.")
        return 8

    try:
        ensure_studio(ROOT, STUDIO_URL)
        relative = accepted.relative_to(ROOT / "web").as_posix()
        post_json(
            STUDIO_URL + "/api/candidate",
            {
                "page_id": "I-01",
                "image_path": relative,
                "qa_status": "pass",
                "supervisor_status": "smoke_test_ready_for_human",
                "candidate_id": f"I-01-SMOKE-A{attempt:03d}",
            },
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Could not register smoke-test candidate: {exc}")
        return 9

    print("\nSUCCESS")
    print(f"Candidate registered in the Studio: {relative}")
    print("Open http://127.0.0.1:8765")
    print("Do not approve automatically; this image is the art-quality calibration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
