from __future__ import annotations

import json
from pathlib import Path

from comfy_cli_runner import ComfyCli, ComfyCliError

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "local_ai_stack.json"
OUT = ROOT / "art_pipeline" / "workflows" / "official"
REPORT = ROOT / "data" / "template-validation.json"


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    cli = ComfyCli()
    results = {}

    for role, name in config["templates"].items():
        path = OUT / f"{name}.json"
        entry = {"name": name, "path": str(path)}
        try:
            entry["fetch"] = cli.fetch_template(name, path)
            entry["slots"] = cli.workflow_slots(path)
            entry["validation"] = cli.validate_workflow(path)
        except ComfyCliError as exc:
            entry["error"] = str(exc)
        results[role] = entry

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(results, indent=2))
    print(f"\nSaved: {REPORT}")
    return 1 if any("error" in item for item in results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
