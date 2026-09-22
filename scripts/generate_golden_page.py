from __future__ import annotations

import argparse
import json
import logging
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from calibration_gate import calibration_case, calibration_paths, load_calibration_config, validate_calibration
from calibration_state import load_calibration_state, register_calibration_candidate, set_calibration_generation_error
from candidate_runner import TechnicalQAError, execute_candidate
from comfy_cli_runner import ComfyCli, ComfyCliError
from comfy_client import ComfyClient
from flux2_klein_profile import envelope_data, prepare_distilled_text_to_image
from generation_runtime import model_filename, read_json
from prompt_builder import build_prompt
from qa import inspect_candidate

LOGGER = logging.getLogger("golden-five")
CONFIG_FILE = ROOT / "config" / "local_ai_stack.json"
WORKFLOW_DIR = ROOT / "art_pipeline" / "workflows" / "official"
MAX_TECHNICAL_RETRIES = 2


def _page(page_id: str, calibration: dict) -> dict:
    paths = calibration_paths(ROOT, calibration)
    try:
        tome = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load calibration source manifest")
        raise RuntimeError(f"Could not load calibration source manifest: {exc}") from exc
    page = next((item for item in tome.get("pages", []) if item.get("page_id") == page_id), None)
    if not page:
        raise RuntimeError(f"Calibration page not found in manifest: {page_id}")
    return page


def _prompt(page: dict, case: dict, page_state: dict) -> str:
    base = build_prompt(page, page_state.get("review_notes"))
    return "\n\n".join([
        base,
        f"GOLDEN FIVE CALIBRATION ROLE: {case['calibration_role']}.",
        "GOLDEN FIVE STRESS TESTS: " + "; ".join(case.get("stress_test") or []) + ".",
        f"GOLDEN FIVE SPECIAL RULE: {case['special_rule']}",
    ])


def _generate(page: dict, case: dict, page_state: dict) -> tuple[str, dict]:
    config = read_json(CONFIG_FILE)
    client = ComfyClient(config["comfy_url"])
    client.health()
    cli = ComfyCli()
    attempt = int(page_state.get("attempt", 0)) + 1

    unet = model_filename(config, "diffusion_models")
    clip = model_filename(config, "text_encoders")
    vae = model_filename(config, "vae")
    workflow = WORKFLOW_DIR / f"golden_{page['page_id'].lower()}_text_to_image.json"

    last_error: Exception | None = None
    for retry in range(MAX_TECHNICAL_RETRIES + 1):
        seed = random.randint(1, 2**63 - 1)
        try:
            meta = prepare_distilled_text_to_image(
                cli,
                config["templates"]["text_to_image"],
                workflow,
                prompt=_prompt(page, case, page_state),
                seed=seed,
                model_filename=unet,
                clip_filename=clip,
                vae_filename=vae,
                width=768,
                height=1024,
            )
            verdict = envelope_data(cli.validate_workflow(workflow)) or {}
            if not verdict.get("valid"):
                raise RuntimeError("Prepared Golden Five workflow failed validation")

            relative = execute_candidate(
                cli, client, workflow, page["page_id"], attempt, inspect_candidate
            )
            source = (ROOT / "web" / relative).resolve()
            output_dir = calibration_paths(ROOT)["output_dir"]
            output_dir.mkdir(parents=True, exist_ok=True)
            destination = output_dir / f"{page['page_id']}-A{attempt:03d}.png"
            shutil.move(str(source), destination)
            return destination.relative_to(ROOT / "web").as_posix(), {
                **meta,
                "seed": seed,
                "technical_retry": retry,
            }
        except (TechnicalQAError, ComfyCliError, OSError, RuntimeError) as exc:
            last_error = exc
            LOGGER.warning(
                "Golden Five generation try %s/%s failed for %s: %s",
                retry + 1,
                MAX_TECHNICAL_RETRIES + 1,
                page["page_id"],
                exc,
            )
    raise RuntimeError(f"Golden Five technical retries exhausted: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one isolated Golden Five calibration candidate")
    parser.add_argument("page_id")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        errors = validate_calibration(ROOT)
        if errors:
            raise RuntimeError("Golden Five configuration invalid: " + " | ".join(errors))
        calibration = load_calibration_config()
        case = calibration_case(args.page_id, calibration)
        state = load_calibration_state(ROOT)
        page_state = state["pages"][args.page_id]
        if page_state.get("status") == "locked":
            raise RuntimeError(f"{args.page_id} is already approved in Golden Five calibration")

        page = _page(args.page_id, calibration)
        image_path, source = _generate(page, case, page_state)
        candidate = register_calibration_candidate(ROOT, args.page_id, image_path, source)
        print(json.dumps(candidate, indent=2))
        return 0
    except Exception as exc:
        LOGGER.exception("Golden Five generation failed")
        try:
            set_calibration_generation_error(ROOT, args.page_id, str(exc))
        except Exception:
            LOGGER.exception("Could not persist Golden Five generation error")
        print(f"GENERATION FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
