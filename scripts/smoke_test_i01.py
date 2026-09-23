from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from comfy_cli_runner import ComfyCli, ComfyCliError
from comfy_client import ComfyClient
from prompt_builder import build_prompt
from page_contract import resolve_page_spec
from qa import inspect_candidate
from flux2_klein_profile import envelope_data, prepare_distilled_text_to_image

TOME_FILE = ROOT / "data" / "tome-I.json"
STATE_FILE = ROOT / "data" / "production-state.json"
CONFIG_FILE = ROOT / "config" / "local_ai_stack.json"
WORKFLOW_DIR = ROOT / "art_pipeline" / "workflows" / "official"
CANDIDATE_DIR = ROOT / "web" / "candidates"
STUDIO_URL = "http://127.0.0.1:8765"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def find_prompt_id(value):
    if isinstance(value, dict):
        if isinstance(value.get("prompt_id"), str):
            return value["prompt_id"]
        for child in value.values():
            found = find_prompt_id(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_prompt_id(child)
            if found:
                return found
    return None


def get_current():
    tome = read_json(TOME_FILE)
    state = read_json(STATE_FILE)
    page_id = state["current_page_id"]
    page = next(p for p in tome["pages"] if p["page_id"] == page_id)
    return resolve_page_spec(page, ROOT), state["pages"][page_id]


def model_filename(config: dict, folder: str) -> str:
    for model in config["models"]:
        if model.get("folder") == folder:
            return model["filename"]
    raise RuntimeError(f"No model configured for {folder}")


def studio_health():
    try:
        with urllib.request.urlopen(STUDIO_URL + "/api/health", timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False


def ensure_studio():
    if studio_health():
        return
    kwargs = {
        "cwd": ROOT,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    subprocess.Popen(
        [sys.executable, str(ROOT / "server.py"), "--no-browser"],
        **kwargs,
    )
    for _ in range(40):
        if studio_health():
            return
        time.sleep(0.25)
    raise RuntimeError("Studio did not start on 127.0.0.1:8765")


def post_json(url: str, payload: dict):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    config = read_json(CONFIG_FILE)
    page, page_state = get_current()
    if page["page_id"] != "I-01":
        print(f"Smoke test is intentionally locked to I-01; current page is {page['page_id']}.")
        return 2

    print("Black-Ink Bestiary — I-01 Local Smoke Test")
    print("==========================================")
    print(f"Page: {page['page_id']} — {page['monster_name']}")

    cli = ComfyCli()
    client = ComfyClient(config["comfy_url"])
    try:
        stats = client.health()
    except Exception as exc:
        print(f"Local ComfyUI is not ready: {exc}")
        print("Run INSTALL_BLACKINK_AI.bat first.")
        return 3

    template_name = config["templates"]["text_to_image"]
    prompt = build_prompt(page, page_state.get("review_notes"))
    seed = random.randint(1, 2**63 - 1)
    workflow_path = WORKFLOW_DIR / "blackink_i01_text_to_image.json"

    try:
        prepared = prepare_distilled_text_to_image(
            cli,
            template_name,
            workflow_path,
            prompt=prompt,
            seed=seed,
            model_filename=model_filename(config, "diffusion_models"),
            clip_filename=model_filename(config, "text_encoders"),
            vae_filename=model_filename(config, "vae"),
            width=768,
            height=1024,
        )
        validation = envelope_data(cli.validate_workflow(workflow_path)) or {}
        if not validation.get("valid"):
            print("Prepared I-01 workflow did not validate:")
            print(json.dumps(validation, indent=2))
            return 4
    except (ComfyCliError, RuntimeError) as exc:
        print(f"Could not prepare the distilled FLUX workflow: {exc}")
        return 4

    print(f"Template: {template_name}")
    print(f"Distilled branch: {prepared['selected_root']}")
    print(f"Model: {model_filename(config, 'diffusion_models')}")
    print(f"Seed: {seed}")
    print("Generating one calibration candidate...")

    try:
        result = cli.run_workflow(workflow_path, timeout=600)
    except ComfyCliError as exc:
        print(exc)
        print("\nIf the error mentions DynamicVRAM/VBAR/CUDA OOM on the RTX 5060 Ti,")
        print("run RESTART_AI_SAFE_MODE.bat and retry this smoke test.")
        return 4

    prompt_id = find_prompt_id(result)
    if not prompt_id:
        print("Generation returned no prompt_id. Machine output:")
        print(json.dumps(result, indent=2))
        return 5

    history = client.history(prompt_id)
    history_entry = history.get(prompt_id)
    if not history_entry:
        print(f"ComfyUI has no completed history entry for {prompt_id}.")
        return 6

    images = client.output_images(history_entry)
    if not images:
        print("Generation completed but no SaveImage output was found.")
        return 7

    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    attempt = int(page_state.get("attempt", 0)) + 1
    accepted = None
    reports = []

    for index, image in enumerate(images, start=1):
        filename = f"I-01-smoke-A{attempt:03d}-{index}.png"
        path = CANDIDATE_DIR / filename
        client.download_image(image, path)
        report = inspect_candidate(path)
        reports.append(report)
        if accepted is None and report.get("pass"):
            accepted = path

    print("\nQA:")
    for report in reports:
        print(f"- {Path(report['path']).name}: {'PASS' if report.get('pass') else 'FAIL'} {report.get('reasons', [])}")

    if accepted is None:
        print("No smoke-test output passed basic production QA.")
        return 8

    ensure_studio()
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

    print("\nSUCCESS")
    print(f"Candidate registered in the Studio: {relative}")
    print("Open http://127.0.0.1:8765")
    print("Do not approve automatically; this first image is the real art-quality calibration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
