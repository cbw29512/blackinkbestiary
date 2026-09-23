from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger("blackink-local-ci")

JSON_FILES = [
    "data/tome-I.json",
    "data/production-state.json",
    "config/studio.json",
    "config/quality_rules.json",
    "config/page_archetypes.json",
    "config/environment_standard.json",
    "config/coloring_page_standard.json",
    "config/universal_page_contract.json",
    "config/universal_monster_contract.json",
    "config/universal_environment_contract.json",
    "config/universal_story_contract.json",
    "config/golden_five_calibration.json",
    "data/golden-five-state.json",
    "config/kdp_print_standard.json",
    "config/content_scope.json",
    "data/monster_source_registry.json",
    "data/environment_variation_families.json",
    "data/environment_overlays.json",
    "data/environment_spatial_envelopes.json",
    "data/scene_relationship_rules.json",
    "data/series.json",
]

NODE_FILES = [
    "web/app.js",
    "web/golden-five-view.js",
    "web/golden-five.js",
]


def validate_json() -> None:
    paths = [ROOT / item for item in JSON_FILES]
    paths.extend(sorted((ROOT / "data" / "environment_components").glob("*.json")))
    for path in paths:
        try:
            with path.open("r", encoding="utf-8") as handle:
                json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"JSON validation failed for {path}: {exc}") from exc
    LOGGER.info("JSON validation passed for %s files", len(paths))


def run(command: list[str]) -> None:
    LOGGER.info("RUN %s", " ".join(command))
    try:
        subprocess.run(command, cwd=ROOT, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Local CI command failed: {' '.join(command)}") from exc


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        validate_json()
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
        run([sys.executable, "scripts/audit_active_book.py"])
        run([sys.executable, "scripts/audit_series.py"])
        run([sys.executable, "-m", "compileall", "-q", "art_pipeline", "scripts", "server.py"])

        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node.js is required for the same JavaScript syntax checks used by CI")
        for path in NODE_FILES:
            run([node, "--check", path])

        LOGGER.info("LOCAL CI PASSED")
        return 0
    except RuntimeError as exc:
        LOGGER.error("LOCAL CI FAILED: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
