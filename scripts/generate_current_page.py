from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from comfy_cli_runner import ComfyCli, ComfyCliError
from comfy_client import ComfyClient
from edit_prompt import build_edit_prompt
from flux2_klein_profile import envelope_data, prepare_distilled_text_to_image
from generation_runtime import (
    collect_output,
    current_context,
    current_source,
    find_prompt_id,
    model_filename,
    post_candidate,
    read_json,
    set_page_status,
)
from image_edit_profile import prepare_distilled_image_edit
from prompt_builder import build_prompt
from qa import inspect_candidate

CONFIG_FILE = ROOT / "config" / "local_ai_stack.json"
WORKFLOW_DIR = ROOT / "art_pipeline" / "workflows" / "official"
GENERATABLE = {"queued", "modify_requested", "regenerate_requested", "generation_failed"}


def prepare_workflow(cli, client, config, page, page_state, status, seed):
    unet = model_filename(config, "diffusion_models")
    clip = model_filename(config, "text_encoders")
    vae = model_filename(config, "vae")

    if status == "modify_requested":
        source = current_source(page_state)
        uploaded = client.upload_image(source, subfolder="blackink-edits")
        path = WORKFLOW_DIR / f"blackink_{page['page_id'].lower()}_image_edit.json"
        meta = prepare_distilled_image_edit(
            cli,
            config["templates"]["modify"],
            path,
            prompt=build_edit_prompt(page, page_state.get("review_notes")),
            seed=seed,
            input_image=uploaded["load_image_name"],
            model_filename=unet,
            clip_filename=clip,
            vae_filename=vae,
        )
        return path, "image_edit", meta

    path = WORKFLOW_DIR / f"blackink_{page['page_id'].lower()}_text_to_image.json"
    meta = prepare_distilled_text_to_image(
        cli,
        config["templates"]["text_to_image"],
        path,
        prompt=build_prompt(page, page_state.get("review_notes")),
        seed=seed,
        model_filename=unet,
        clip_filename=clip,
        vae_filename=vae,
        width=768,
        height=1024,
    )
    return path, "text_to_image", meta


def run_generation(page: dict, page_state: dict, starting_status: str) -> None:
    config = read_json(CONFIG_FILE)
    client = ComfyClient(config["comfy_url"])
    client.health()
    cli = ComfyCli()
    seed = random.randint(1, 2**63 - 1)

    workflow, mode, meta = prepare_workflow(
        cli, client, config, page, page_state, starting_status, seed
    )
    verdict = envelope_data(cli.validate_workflow(workflow)) or {}
    if not verdict.get("valid"):
        raise RuntimeError("Prepared workflow failed validation: " + json.dumps(verdict))

    print(f"Generating {page['page_id']} - {page['monster_name']} via {mode}")
    print(f"Seed: {seed}")
    result = cli.run_workflow(workflow, timeout=600)
    pid = find_prompt_id(result)
    if not pid:
        raise RuntimeError("ComfyUI generation returned no prompt_id")

    history = client.history(pid).get(pid)
    if not history:
        raise RuntimeError(f"ComfyUI has no completed history entry for {pid}")
    images = client.output_images(history)
    if not images:
        raise RuntimeError("Generation completed but no SaveImage output was found")

    attempt = int(page_state.get("attempt", 0)) + 1
    relative = collect_output(client, images, page["page_id"], attempt, inspect_candidate)
    post_candidate({
        "page_id": page["page_id"],
        "image_path": relative,
        "qa_status": "pass",
        "supervisor_status": f"{mode}_ready_for_human",
        "candidate_id": f"{page['page_id']}-A{attempt:03d}",
        "generation_mode": mode,
        "source": meta,
    })
    print(f"SUCCESS: {page['page_id']} {mode} candidate registered at {relative}")


def main() -> int:
    page, page_state = current_context()
    page_id = page["page_id"]
    starting = page_state["status"]
    if starting not in GENERATABLE:
        print(f"{page_id} is not ready for generation: {starting}")
        return 2

    set_page_status(page_id, "generating")
    try:
        run_generation(page, page_state, starting)
        return 0
    except (ComfyCliError, Exception) as exc:
        fallback = (
            starting
            if starting in {"modify_requested", "regenerate_requested"}
            else "generation_failed"
        )
        set_page_status(page_id, fallback, str(exc))
        print(f"GENERATION FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
