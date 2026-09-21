from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from comfy_client import ComfyClient, ComfyError
from prompt_builder import build_prompt, build_supervisor_checklist
from workflow_adapter import load_workflow, prepare_workflow, validate_template

ROOT = Path(__file__).resolve().parents[1]
TOME_FILE = ROOT / "data" / "tome-I.json"
STATE_FILE = ROOT / "data" / "production-state.json"
WORKFLOW_FILE = Path(__file__).resolve().parent / "workflows" / "flux2_klein_api.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def current_context():
    tome = read_json(TOME_FILE)
    state = read_json(STATE_FILE)
    page_id = state["current_page_id"]
    page = next(page for page in tome["pages"] if page["page_id"] == page_id)
    page_state = state["pages"][page_id]
    return page, page_state


def readiness(comfy_url: str):
    page, page_state = current_context()
    prompt = build_prompt(page, page_state.get("review_notes"))
    report = {
        "current_page": page["page_id"],
        "monster": page["monster_name"],
        "prompt_ready": bool(prompt),
        "workflow_file": str(WORKFLOW_FILE),
        "workflow_ready": False,
        "comfy_url": comfy_url,
        "comfy_ready": False,
    }

    if WORKFLOW_FILE.exists():
        workflow = load_workflow(WORKFLOW_FILE)
        problems = validate_template(workflow)
        report["workflow_ready"] = not problems
        report["workflow_problems"] = problems
    else:
        report["workflow_problems"] = ["workflow API template not installed yet"]

    try:
        stats = ComfyClient(comfy_url).health()
        report["comfy_ready"] = True
        report["comfy_devices"] = stats.get("devices", [])
    except ComfyError as exc:
        report["comfy_error"] = str(exc)

    return report


def show_prompt():
    page, page_state = current_context()
    print(build_prompt(page, page_state.get("review_notes")))
    print("\n--- SUPERVISOR CHECKLIST ---")
    for item in build_supervisor_checklist(page):
        print(f"- {item}")


def submit_one(comfy_url: str, seed: int | None):
    page, page_state = current_context()
    if not WORKFLOW_FILE.exists():
        raise SystemExit(
            f"Missing {WORKFLOW_FILE}. Run --check and install the approved workflow template before generation."
        )
    template = load_workflow(WORKFLOW_FILE)
    problems = validate_template(template)
    if problems:
        raise SystemExit("Workflow template invalid: " + "; ".join(problems))

    prompt = build_prompt(page, page_state.get("review_notes"))
    seed = seed if seed is not None else random.randint(1, 2**63 - 1)
    workflow = prepare_workflow(template, prompt=prompt, seed=seed)

    client = ComfyClient(comfy_url)
    prompt_id = client.queue_prompt(workflow)
    print(f"Queued {page['page_id']} as ComfyUI prompt {prompt_id}")
    history = client.wait(prompt_id)
    images = client.output_images(history)
    if not images:
        raise SystemExit("ComfyUI completed but returned no output images")
    print(json.dumps({"prompt_id": prompt_id, "seed": seed, "images": images}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Black-Ink Bestiary local art worker")
    parser.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--prompt", action="store_true")
    group.add_argument("--generate-one", action="store_true")
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()

    if args.check:
        print(json.dumps(readiness(args.comfy_url), indent=2))
        return
    if args.prompt:
        show_prompt()
        return
    if args.generate_one:
        submit_one(args.comfy_url, args.seed)


if __name__ == "__main__":
    main()
