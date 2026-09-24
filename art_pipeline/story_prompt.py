from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILE = ROOT / "config" / "universal_story_contract.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_story_contract(root: Path = ROOT) -> dict:
    return _read(root / "config" / "universal_story_contract.json")


def critical_scene_lock(page: dict) -> str:
    variant = page.get("environment_variant") or {}
    physicality = page.get("physicality") or {}
    return (
        "CRITICAL SCENE LOCK — NON-NEGOTIABLE: "
        f"exact visible action={page.get('moment', '')}; "
        f"environment interaction={variant.get('interaction', '')}; "
        f"landmark={variant.get('landmark', '')}; "
        f"framing={variant.get('framing', '')}; "
        f"support/contact={physicality.get('support', '')}; "
        f"motion/weight={physicality.get('motion', '')}. "
        "Build the pose and environment around this cause-and-effect first. "
        "Do not replace the required action with standing, holding, posing, or merely being near the prop."
    )


def story_sections(page: dict, root: Path = ROOT) -> list[str]:
    contract = load_story_contract(root)
    variant = page.get("environment_variant") or {}
    physicality = page.get("physicality") or {}
    return [
        f"STORY BEAT: {page.get('moment', '')}.",
        f"STORY/ENVIRONMENT INTERACTION: {variant.get('interaction', '')}.",
        f"STORY BODY LANGUAGE: {physicality.get('motion', '')}.",
        f"STORY PRIORITY: {contract.get('priority_rule', '')}",
        "STORY RULES: " + "; ".join(contract.get("principles") or []) + ".",
        (
            "STATIC STORY TEST: the page must read as one clear verb/action at thumbnail size, "
            "not as a character portrait or a monster merely holding props. "
            "If extra story detail would reduce coloring space or silhouette clarity, simplify the story."
        ),
    ]


def story_checklist(page: dict, root: Path = ROOT) -> list[str]:
    contract = load_story_contract(root)
    checks = [
        f"One clear story beat reads as: {page.get('moment', '')}",
        f"Environment participates through: {(page.get('environment_variant') or {}).get('interaction', '')}",
        "Body language communicates the action without needing the caption",
        "The page does not read as a neutral portrait or prop-holding pose",
    ]
    checks.extend(contract.get("review_questions") or [])
    return checks


def story_errors(page: dict, root: Path = ROOT) -> list[str]:
    contract = load_story_contract(root)
    moment = " ".join(str(page.get("moment") or "").strip().lower().split())
    generic = {
        "standing",
        "posing",
        "waiting",
        "idle",
        "ready",
        "holding something",
        "holding a weapon",
    }
    errors = []
    if moment in generic:
        errors.append(f"{page.get('page_id')}: story moment is too generic for a production page")
    interaction = str((page.get("environment_variant") or {}).get("interaction") or "").strip()
    if not interaction:
        errors.append(f"{page.get('page_id')}: story/environment interaction is required")
    motion = str((page.get("physicality") or {}).get("motion") or "").strip()
    if not motion:
        errors.append(f"{page.get('page_id')}: story body language/physical motion is required")
    return errors
