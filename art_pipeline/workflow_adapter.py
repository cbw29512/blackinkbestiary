from __future__ import annotations

import copy
import json
from pathlib import Path


PROMPT_TOKEN = "__BLACKINK_PROMPT__"
SEED_TOKEN = "__BLACKINK_SEED__"


def load_workflow(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _replace(value, prompt: str, seed: int):
    if isinstance(value, dict):
        return {k: _replace(v, prompt, seed) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace(v, prompt, seed) for v in value]
    if value == PROMPT_TOKEN:
        return prompt
    if value == SEED_TOKEN:
        return seed
    return value


def prepare_workflow(template: dict, *, prompt: str, seed: int) -> dict:
    prepared = _replace(copy.deepcopy(template), prompt, seed)
    encoded = json.dumps(prepared)
    if PROMPT_TOKEN in encoded:
        raise ValueError("Prompt token was not fully replaced")
    if SEED_TOKEN in encoded:
        raise ValueError("Seed token was not fully replaced")
    return prepared


def validate_template(template: dict) -> list[str]:
    encoded = json.dumps(template)
    problems = []
    if PROMPT_TOKEN not in encoded:
        problems.append(f"missing prompt token {PROMPT_TOKEN}")
    if SEED_TOKEN not in encoded:
        problems.append(f"missing seed token {SEED_TOKEN}")
    return problems
