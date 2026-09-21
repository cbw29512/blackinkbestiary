from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

import requests
from PIL import Image, ImageOps

from worker.comfy_client import ComfyClient, ComfyError
from worker.prompt_builder import build_edit_prompt, build_generation_prompt
from worker.qa import choose_best, inspect
from worker.workflows import image_edit, text_to_image

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "worker" / "config.json"
WEB_DIR = ROOT / "web"
CANDIDATE_DIR = WEB_DIR / "candidates"
REQUIRED_NODES = {
    "UNETLoader", "CLIPLoader", "VAELoader", "CLIPTextEncode",
    "ConditioningZeroOut", "CFGGuider", "RandomNoise", "KSamplerSelect",
    "Flux2Scheduler", "EmptyFlux2LatentImage", "SamplerCustomAdvanced",
    "VAEDecode", "SaveImage", "LoadImage", "VAEEncode", "ReferenceLatent",
}


def load_config():
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def studio_get(cfg, path):
    r = requests.get(cfg["studio_url"].rstrip("/") + path, timeout=20)
    r.raise_for_status()
    return r.json()


def studio_post(cfg, path, payload):
    r = requests.post(cfg["studio_url"].rstrip("/") + path, json=payload, timeout=20)
    if not r.ok:
        raise RuntimeError(f"Studio rejected request: {r.status_code} {r.text}")
    return r.json()


def set_status(cfg, page_id, status, message):
    try:
        studio_post(cfg, "/api/worker-status", {
            "page_id": page_id,
            "status": status,
            "message": message,
        })
    except Exception:
        pass


def prepare_reference(source: Path, width: int, height: int) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"Reference image not found: {source}")
    with Image.open(source) as im:
        rgb = im.convert("RGB")
        contained = ImageOps.contain(rgb, (width, height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (width, height), "white")
        x = (width - contained.width) // 2
        y = (height - contained.height) // 2
        canvas.paste(contained, (x, y))
        tmp = Path(tempfile.gettempdir()) / "blackinkbestiary-reference.png"
        canvas.save(tmp, format="PNG")
        return tmp


def run_once() -> int:
    cfg = load_config()
    state = studio_get(cfg, "/api/state")
    page = state["current_page"]
    page_state = state["current_state"]
    page_id = page["page_id"]
    status = page_state["status"]

    if status == "awaiting_human":
        print(f"{page_id} is already waiting for human review. No generation needed.")
        return 0
    if status == "locked":
        print(f"{page_id} is locked. No generation needed.")
        return 0
    if status not in {"queued", "modify_requested", "regenerate_requested"}:
        print(f"{page_id} is in state {status}; worker will not interfere.")
        return 0

    comfy = ComfyClient(cfg["comfy_url"])
    print("Checking ComfyUI...")
    comfy.health()
    comfy.validate_nodes(REQUIRED_NODES)

    width = int(cfg["image"]["width"])
    height = int(cfg["image"]["height"])
    count = int(cfg["generation"]["candidate_count"])
    timeout = int(cfg["generation"]["timeout_seconds"])
    existing_review = page_state.get("review_notes") or {}

    reference_rel = page.get("reference_image")
    use_edit = bool(reference_rel) and status == "modify_requested"
    if use_edit:
        prompt = build_edit_prompt(page, existing_review)
        reference_path = WEB_DIR / reference_rel
        prepared = prepare_reference(reference_path, width, height)
        uploaded = comfy.upload_image(prepared, f"{page_id}-reference.png")
        mode = "targeted_edit"
    else:
        prompt = build_generation_prompt(page)
        uploaded = None
        mode = "fresh_generation"

    set_status(cfg, page_id, "generating", f"Generating {count} candidates")
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for index in range(1, count + 1):
        seed = random.SystemRandom().randrange(1, 2**48)
        prefix = f"BlackInkBestiary/{page_id}/candidate-{index:02d}"
        if use_edit:
            graph = image_edit(prompt, seed, cfg, prefix, uploaded)
        else:
            graph = text_to_image(prompt, seed, cfg, prefix)

        print(f"[{index}/{count}] {page_id} seed {seed}")
        prompt_id = comfy.queue(graph)
        images = comfy.wait_for_images(prompt_id, timeout)
        if not images:
            continue

        destination = CANDIDATE_DIR / f"{page_id}-candidate-{index:02d}.png"
        comfy.download_image(images[0], destination)
        qa = inspect(destination, target_ratio=width / height)
        results.append({
            "path": destination,
            "relative": f"candidates/{destination.name}",
            "seed": seed,
            "qa": qa,
        })
        print(f"  QA {'PASS' if qa['passed'] else 'FAIL'} score={qa['score']}")

    set_status(cfg, page_id, "qa_review", "Ranking candidates with coloring-page QA")
    best = choose_best(results)
    if best is None:
        set_status(cfg, page_id, status, "All candidates failed automatic QA; page remains current")
        print("No candidate passed QA. Nothing was submitted to the review studio.")
        for item in results:
            print(f"- {item['path'].name}: {', '.join(item['qa']['reasons']) or 'failed'}")
        return 2

    set_status(cfg, page_id, "supervisor_review", "Best technical candidate selected; awaiting visual human review")
    payload = {
        "page_id": page_id,
        "image_path": best["relative"],
        "candidate_id": f"{page_id}-{mode}-{best['seed']}",
        "qa_status": "pass",
        "qa_score": best["qa"]["score"],
        "qa_details": best["qa"],
        "supervisor_status": "preflight_pass",
        "seed": best["seed"],
        "generation_mode": mode,
        "prompt": prompt,
    }
    studio_post(cfg, "/api/candidate", payload)
    print(f"Submitted {best['path'].name} to the Studio for human review.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Black-Ink Bestiary local art worker")
    parser.add_argument("--check", action="store_true", help="Check Studio and ComfyUI connections only")
    args = parser.parse_args()
    cfg = load_config()

    try:
        if args.check:
            studio_get(cfg, "/api/health")
            comfy = ComfyClient(cfg["comfy_url"])
            comfy.health()
            comfy.validate_nodes(REQUIRED_NODES)
            print("Studio: OK")
            print("ComfyUI: OK")
            print("Required nodes: OK")
            return 0
        return run_once()
    except (requests.RequestException, ComfyError, FileNotFoundError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
