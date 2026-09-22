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
from image_edit_profile import prepare_distilled_image_edit
from prompt_builder import build_edit_prompt, build_prompt
from qa import inspect_candidate

TOME_FILE = ROOT / "data" / "tome-I.json"
STATE_FILE = ROOT / "data" / "production-state.json"
CONFIG_FILE = ROOT / "config" / "local_ai_stack.json"
WORKFLOW_DIR = ROOT / "art_pipeline" / "workflows" / "official"
CANDIDATE_DIR = ROOT / "web" / "candidates"
WEB_DIR = ROOT / "web"
STUDIO_URL = "http://127.0.0.1:8765"
GENERATABLE = {"queued", "modify_requested", "regenerate_requested", "generation_failed"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def context():
    tome = read_json(TOME_FILE)
    state = read_json(STATE_FILE)
    page_id = state["current_page_id"]
    page = next(item for item in tome["pages"] if item["page_id"] == page_id)
    return page, state["pages"][page_id]


def set_status(page_id: str, status: str, error: str | None = None) -> None:
    state = read_json(STATE_FILE)
    if state["current_page_id"] != page_id:
        return
    entry = state["pages"][page_id]
    entry["status"] = status
    if error:
        entry["generation_error"] = {"message": error, "at": now()}
    else:
        entry.pop("generation_error", None)
    state["updated_at"] = now()
    write_json(STATE_FILE, state)


def model(config: dict, folder: str) -> str:
    match = next((item for item in config["models"] if item.get("folder") == folder), None)
    if not match:
        raise RuntimeError(f"No model configured for {folder}")
    return match["filename"]


def prompt_id(value):
    if isinstance(value, dict):
        if isinstance(value.get("prompt_id"), str):
            return value["prompt_id"]
        for child in value.values():
            found = prompt_id(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = prompt_id(child)
            if found:
                return found
    return None


def post_candidate(payload: dict) -> None:
    request = urllib.request.Request(
        STUDIO_URL + "/api/candidate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def current_source(page_state: dict) -> Path:
    candidate = page_state.get("current_candidate") or {}
    relative = Path(str(candidate.get("image_path") or ""))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("Modify requires a safe current candidate image path")
    source = (WEB_DIR / relative).resolve()
    if WEB_DIR.resolve() not in source.parents or not source.exists():
        raise RuntimeError(f"Modify source image is missing: {relative.as_posix()}")
    return source


def prepare(cli, client, config, page, page_state, status, seed):
    unet = model(config, "diffusion_models")
    clip = model(config, "text_encoders")
    vae = model(config, "vae")
    if status == "modify_requested":
        source = current_source(page_state)
        uploaded = client.upload_image(source, subfolder="blackink-edits")
        path = WORKFLOW_DIR / f"blackink_{page['page_id'].lower()}_image_edit.json"
        meta = prepare_distilled_image_edit(
            cli, config["templates"]["modify"], path,
            prompt=build_edit_prompt(page, page_state.get("review_notes")),
            seed=seed, input_image=uploaded["load_image_name"],
            model_filename=unet, clip_filename=clip, vae_filename=vae,
        )
        return path, "image_edit", meta

    path = WORKFLOW_DIR / f"blackink_{page['page_id'].lower()}_text_to_image.json"
    meta = prepare_distilled_text_to_image(
        cli, config["templates"]["text_to_image"], path,
        prompt=build_prompt(page, page_state.get("review_notes")),
        seed=seed, model_filename=unet, clip_filename=clip, vae_filename=vae,
        width=768, height=1024,
    )
    return path, "text_to_image", meta


def main() -> int:
    page, page_state = context()
    page_id = page["page_id"]
    starting = page_state["status"]
    if starting not in GENERATABLE:
        print(f"{page_id} is not ready for generation: {starting}")
        return 2

    set_status(page_id, "generating")
    try:
        config = read_json(CONFIG_FILE)
        client = ComfyClient(config["comfy_url"])
        client.health()
        cli = ComfyCli()
        seed = random.randint(1, 2**63 - 1)
        workflow, mode, meta = prepare(cli, client, config, page, page_state, starting, seed)

        verdict = envelope_data(cli.validate_workflow(workflow)) or {}
        if not verdict.get("valid"):
            raise RuntimeError("Prepared workflow failed validation: " + json.dumps(verdict))

        print(f"Generating {page_id} - {page['monster_name']} via {mode}")
        print(f"Seed: {seed}")
        result = cli.run_workflow(workflow, timeout=600)
        pid = prompt_id(result)
        if not pid:
            raise RuntimeError("ComfyUI generation returned no prompt_id")

        history = client.history(pid).get(pid)
        if not history:
            raise RuntimeError(f"ComfyUI has no completed history entry for {pid}")
        images = client.output_images(history)
        if not images:
            raise RuntimeError("Generation completed but no SaveImage output was found")

        attempt = int(page_state.get("attempt", 0)) + 1
        CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
        accepted = None
        reports = []
        for index, image in enumerate(images, 1):
            destination = CANDIDATE_DIR / f"{page_id}-A{attempt:03d}-{index}.png"
            client.download_image(image, destination)
            report = inspect_candidate(destination)
            reports.append(report)
            if accepted is None and report.get("pass"):
                accepted = destination
        if accepted is None:
            raise RuntimeError(f"No output passed production QA: {[r.get('reasons') for r in reports]}")

        relative = accepted.relative_to(WEB_DIR).as_posix()
        post_candidate({
            "page_id": page_id, "image_path": relative, "qa_status": "pass",
            "supervisor_status": f"{mode}_ready_for_human",
            "candidate_id": f"{page_id}-A{attempt:03d}",
            "generation_mode": mode, "source": meta,
        })
        print(f"SUCCESS: {page_id} {mode} candidate registered at {relative}")
        return 0
    except (ComfyCliError, Exception) as exc:
        fallback = starting if starting in {"modify_requested", "regenerate_requested"} else "generation_failed"
        set_status(page_id, fallback, str(exc))
        print(f"GENERATION FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
