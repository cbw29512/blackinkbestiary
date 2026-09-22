from __future__ import annotations

import json
import random
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from comfy_cli_runner import ComfyCli, ComfyCliError
from comfy_client import ComfyClient
from flux2_klein_profile import envelope_data, prepare_distilled_text_to_image
from prompt_builder import build_prompt
from qa import inspect_candidate

TOME_FILE = ROOT / "data" / "tome-I.json"
STATE_FILE = ROOT / "data" / "production-state.json"
CONFIG_FILE = ROOT / "config" / "local_ai_stack.json"
WORKFLOW_DIR = ROOT / "art_pipeline" / "workflows" / "official"
CANDIDATE_DIR = ROOT / "web" / "candidates"
STUDIO_URL = "http://127.0.0.1:8765"

GENERATABLE_STATES = {"queued", "modify_requested", "regenerate_requested", "generation_failed"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def current_context():
    tome = read_json(TOME_FILE)
    state = read_json(STATE_FILE)
    page_id = state["current_page_id"]
    page = next(p for p in tome["pages"] if p["page_id"] == page_id)
    return page, state, state["pages"][page_id]


def set_page_status(page_id: str, status: str, *, error: str | None = None) -> None:
    state = read_json(STATE_FILE)
    if state["current_page_id"] != page_id:
        return
    page_state = state["pages"][page_id]
    page_state["status"] = status
    if error:
        page_state["generation_error"] = {"message": error, "at": utc_now()}
    else:
        page_state.pop("generation_error", None)
    state["updated_at"] = utc_now()
    write_json(STATE_FILE, state)


def model_filename(config: dict, folder: str) -> str:
    for model in config["models"]:
        if model.get("folder") == folder:
            return model["filename"]
    raise RuntimeError(f"No model configured for {folder}")


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


def post_json(path: str, payload: dict):
    request = urllib.request.Request(
        STUDIO_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    page, _, page_state = current_context()
    page_id = page["page_id"]
    starting_status = page_state["status"]

    if starting_status not in GENERATABLE_STATES:
        print(f"{page_id} is not ready for generation: {starting_status}")
        return 2

    set_page_status(page_id, "generating")
    try:
        config = read_json(CONFIG_FILE)
        client = ComfyClient(config["comfy_url"])
        client.health()

        prompt = build_prompt(page, page_state.get("review_notes"))
        seed = random.randint(1, 2**63 - 1)
        workflow_path = WORKFLOW_DIR / f"blackink_{page_id.lower()}_text_to_image.json"
        cli = ComfyCli()

        prepared = prepare_distilled_text_to_image(
            cli,
            config["templates"]["text_to_image"],
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
            raise RuntimeError("Prepared workflow failed validation: " + json.dumps(validation))

        print(f"Generating {page_id} - {page['monster_name']}")
        print(f"Distilled branch: {prepared['selected_root']}")
        print(f"Seed: {seed}")

        result = cli.run_workflow(workflow_path, timeout=600)
        prompt_id = find_prompt_id(result)
        if not prompt_id:
            raise RuntimeError("ComfyUI generation returned no prompt_id")

        history = client.history(prompt_id)
        history_entry = history.get(prompt_id)
        if not history_entry:
            raise RuntimeError(f"ComfyUI has no completed history entry for {prompt_id}")

        images = client.output_images(history_entry)
        if not images:
            raise RuntimeError("Generation completed but no SaveImage output was found")

        attempt = int(page_state.get("attempt", 0)) + 1
        CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
        accepted = None
        reports = []

        for index, image in enumerate(images, start=1):
            filename = f"{page_id}-A{attempt:03d}-{index}.png"
            destination = CANDIDATE_DIR / filename
            client.download_image(image, destination)
            report = inspect_candidate(destination)
            reports.append(report)
            if accepted is None and report.get("pass"):
                accepted = destination

        if accepted is None:
            reasons = [r.get("reasons", []) for r in reports]
            raise RuntimeError(f"No generated image passed basic production QA: {reasons}")

        relative = accepted.relative_to(ROOT / "web").as_posix()
        post_json(
            "/api/candidate",
            {
                "page_id": page_id,
                "image_path": relative,
                "qa_status": "pass",
                "supervisor_status": "ready_for_human",
                "candidate_id": f"{page_id}-A{attempt:03d}",
            },
        )
        print(f"SUCCESS: {page_id} candidate registered at {relative}")
        return 0
    except (ComfyCliError, Exception) as exc:
        message = str(exc)
        fallback = starting_status if starting_status in {"modify_requested", "regenerate_requested"} else "generation_failed"
        set_page_status(page_id, fallback, error=message)
        print(f"GENERATION FAILED: {message}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
