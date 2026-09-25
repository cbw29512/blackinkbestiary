from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

try:
    from .book_promotion import build_manifest_from_plan
    from .book_scaffold import build_book_plan, build_book_record
    from .generation_lint import generation_lint_errors
    from .manifest_validation import validate_manifest
    from .prompt_builder import build_prompt
except ImportError:
    from book_promotion import build_manifest_from_plan
    from book_scaffold import build_book_plan, build_book_record
    from generation_lint import generation_lint_errors
    from manifest_validation import validate_manifest
    from prompt_builder import build_prompt

ROOT = Path(__file__).resolve().parents[1]
PROBE_SOURCE_PAGE_IDS = ("I-01", "I-16", "I-22")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _probe_source_pages(root: Path) -> list[dict]:
    tome = _read(root / "data" / "tome-I.json")
    by_id = {str(page.get("page_id")): page for page in tome.get("pages", [])}
    missing = [page_id for page_id in PROBE_SOURCE_PAGE_IDS if page_id not in by_id]
    if missing:
        raise RuntimeError("replication probe source pages missing: " + ", ".join(missing))
    return [deepcopy(by_id[page_id]) for page_id in PROBE_SOURCE_PAGE_IDS]


def run_replication_probe(root: Path = ROOT) -> dict:
    """Prove a future tome can reach the GPU boundary without bespoke engine code."""
    errors: list[str] = []
    stages = {
        "scaffold": False,
        "manifest_promotion": False,
        "manifest_validation": False,
        "prompt_resolution": False,
        "pre_gpu_lint": False,
    }

    try:
        sources = _probe_source_pages(root)
        book = build_book_record(
            "TOME-IX-SYNTHETIC",
            "Synthetic Replication Probe",
            "Temporary non-GPU probe for reusable production machinery.",
            len(sources),
            ["underground"],
        )
        plan = build_book_plan(book, "IX")
        stages["scaffold"] = len(plan.get("slots") or []) == len(sources)

        for order, (slot, source) in enumerate(zip(plan["slots"], sources), start=1):
            page = deepcopy(source)
            page["page_id"] = f"IX-{order:02d}"
            page["order"] = order
            page["planning_status"] = "ready"
            slot.update(page)

        manifest, promotion_errors = build_manifest_from_plan(plan, root)
        if promotion_errors:
            errors.extend("promotion: " + error for error in promotion_errors)
        else:
            stages["manifest_promotion"] = True

        manifest_errors = validate_manifest(
            root,
            manifest,
            root / "data" / "monsters",
        )
        if manifest_errors:
            errors.extend("manifest: " + error for error in manifest_errors)
        else:
            stages["manifest_validation"] = True

        prompt_errors = []
        lint_errors = []
        for page in manifest.get("pages", []):
            try:
                prompt = build_prompt(page)
                if not prompt.strip():
                    prompt_errors.append(f"{page.get('page_id')}: empty prompt")
                    continue
                for error in generation_lint_errors(page, prompt, root):
                    lint_errors.append(error)
            except Exception as exc:
                prompt_errors.append(f"{page.get('page_id')}: {exc}")

        if prompt_errors:
            errors.extend("prompt: " + error for error in prompt_errors)
        else:
            stages["prompt_resolution"] = True
        if lint_errors:
            errors.extend("lint: " + error for error in lint_errors)
        elif not prompt_errors:
            stages["pre_gpu_lint"] = True
    except Exception as exc:
        errors.append(f"probe_exception: {exc}")

    return {
        "schema_version": 1,
        "probe_id": "synthetic-tome-ix-pre-gpu-v1",
        "pages": len(PROBE_SOURCE_PAGE_IDS),
        "stages": stages,
        "pass": all(stages.values()) and not errors,
        "errors": errors,
    }
