from __future__ import annotations

import json
import re
from pathlib import Path

try:
    from .monster_catalog import load_monster_for_page
except ImportError:
    from monster_catalog import load_monster_for_page

ROOT = Path(__file__).resolve().parents[1]


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _prompt_budget(root: Path = ROOT) -> dict:
    path = root / "config" / "coloring_page_standard.json"
    defaults = {"hard_max_chars": 14000, "hard_max_words": 2000}
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    budget = config.get("generation_prompt_budget") or {}
    return {
        "hard_max_chars": int(budget.get("hard_max_chars") or defaults["hard_max_chars"]),
        "hard_max_words": int(budget.get("hard_max_words") or defaults["hard_max_words"]),
    }


def generation_lint_errors(page: dict, prompt: str, root: Path = ROOT) -> list[str]:
    """Fail cheap before GPU work when resolved generation authority is incomplete."""
    errors: list[str] = []
    text = str(prompt or "")
    normalized_prompt = _norm(text)
    page_id = str(page.get("page_id") or "<unknown>")

    if not text.strip():
        return [f"{page_id}: prompt is empty"]

    budget = _prompt_budget(root)
    if len(text) > budget["hard_max_chars"]:
        errors.append(
            f"{page_id}: generation prompt exceeds hard character budget "
            f"({len(text)} > {budget['hard_max_chars']})"
        )
    word_count = len(text.split())
    if word_count > budget["hard_max_words"]:
        errors.append(
            f"{page_id}: generation prompt exceeds hard word budget "
            f"({word_count} > {budget['hard_max_words']})"
        )

    for token in ("<missing>", "TODO", "TBD"):
        if token.lower() in text.lower():
            errors.append(f"{page_id}: unresolved placeholder {token!r} reached generation prompt")

    subject = str(page.get("monster_name") or "").strip()
    if subject and f"SUBJECT: {subject}." not in text:
        errors.append(f"{page_id}: resolved subject missing from prompt")

    spec = load_monster_for_page(page, root / "data" / "monsters")
    visual = (spec or {}).get("visual_identity") or {}
    for field in ("shape_lock", "limb_structure"):
        value = str(visual.get(field) or "").strip()
        if not value:
            errors.append(f"{page_id}: monster {field} is empty")
        elif _norm(value) not in normalized_prompt:
            errors.append(f"{page_id}: monster {field} authority missing from final prompt")

    variant = page.get("environment_variant") or {}
    for field in ("landmark", "framing", "interaction"):
        value = str(variant.get(field) or "").strip()
        if not value:
            errors.append(f"{page_id}: environment_variant.{field} is empty")
        elif _norm(value) not in normalized_prompt:
            errors.append(
                f"{page_id}: environment_variant.{field} missing from final prompt"
            )

    physicality = page.get("physicality") or {}
    for field in ("support", "motion"):
        value = str(physicality.get(field) or "").strip()
        if not value:
            errors.append(f"{page_id}: physicality.{field} is empty")
        elif _norm(value) not in normalized_prompt:
            errors.append(f"{page_id}: physicality.{field} missing from final prompt")

    includes = {_norm(item): str(item) for item in page.get("must_include") or [] if _norm(item)}
    avoids = {_norm(item): str(item) for item in page.get("must_avoid") or [] if _norm(item)}
    conflicts = sorted(set(includes) & set(avoids))
    for key in conflicts:
        errors.append(
            f"{page_id}: exact requirement conflict: {includes[key]!r} is both must_include and must_avoid"
        )

    for required in (
        "PAGE RECIPE LOCK — NON-NEGOTIABLE:",
        "ANATOMICAL INTEGRITY LOCK — NON-NEGOTIABLE:",
        "MODEL ENVIRONMENT PRIORITY CAPSULE",
    ):
        if required not in text:
            errors.append(f"{page_id}: required generation lock missing: {required}")

    return errors


def assert_generation_ready(page: dict, prompt: str, root: Path = ROOT) -> None:
    errors = generation_lint_errors(page, prompt, root)
    if errors:
        raise RuntimeError("generation_lint_failed: " + " | ".join(errors))
