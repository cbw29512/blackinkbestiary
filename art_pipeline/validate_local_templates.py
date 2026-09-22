from __future__ import annotations

import json
from pathlib import Path

from comfy_cli_runner import ComfyCli, ComfyCliError
from flux2_klein_profile import envelope_data, prepare_distilled_text_to_image

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "local_ai_stack.json"
OUT = ROOT / "art_pipeline" / "workflows" / "official"
REPORT = ROOT / "data" / "template-validation.json"


def diffusion_model_filename(config: dict) -> str:
    for model in config["models"]:
        if model.get("folder") == "diffusion_models":
            return model["filename"]
    raise RuntimeError("No diffusion model configured")


def validation_data(payload: dict) -> dict:
    data = envelope_data(payload)
    return data if isinstance(data, dict) else {}


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    cli = ComfyCli()
    results = {}
    failed = False

    print("Black-Ink Bestiary - Official Workflow Validation")
    print("==================================================")

    for role, name in config["templates"].items():
        entry = {"name": name}
        try:
            if role == "text_to_image":
                path = OUT / f"{name}.blackink.json"
                prep = prepare_distilled_text_to_image(
                    cli,
                    name,
                    path,
                    prompt="Black-Ink Bestiary validation prompt",
                    seed=1,
                    model_filename=diffusion_model_filename(config),
                    width=768,
                    height=1024,
                )
                entry["prepared"] = prep
            else:
                path = OUT / f"{name}.json"
                entry["fetch"] = cli.fetch_template(name, path)

            slots_payload = envelope_data(cli.workflow_slots(path)) or {}
            slots = slots_payload.get("slots") if isinstance(slots_payload, dict) else []
            entry["slot_count"] = len(slots) if isinstance(slots, list) else 0

            validation = cli.validate_workflow(path)
            entry["validation"] = validation
            verdict = validation_data(validation)
            valid = bool(verdict.get("valid"))
            errors = int(verdict.get("error_count", 0) or 0)
            warnings = int(verdict.get("warning_count", 0) or 0)
            entry["valid"] = valid

            mark = "PASS" if valid else "FAIL"
            print(f"[{mark}] {role}: {name} (errors={errors}, warnings={warnings})")
            if not valid:
                failed = True
                for error in verdict.get("errors", [])[:8]:
                    print(f"       - {error.get('code')}: {error.get('message')}")
        except (ComfyCliError, RuntimeError) as exc:
            entry["error"] = str(exc)
            failed = True
            print(f"[FAIL] {role}: {name}")
            print(f"       {exc}")

        entry["path"] = str(path) if "path" in locals() else None
        results[role] = entry

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"Saved detailed report: {REPORT}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
