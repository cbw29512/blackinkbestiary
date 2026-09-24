from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Raw-file hashing is reserved for execution code that can change pixels even
# when the resolved text prompt is identical. Prompt-construction authority is
# hashed through the actual candidate prompts below so unrelated helper/comment
# edits do not force expensive rerenders.
GENERATION_EXECUTION_FILES = (
    "art_pipeline/flux2_klein_profile.py",
    "art_pipeline/generation_runtime.py",
    "art_pipeline/workflow_adapter.py",
)

REVIEW_AUTHORITY_FILES = (
    "art_pipeline/vision_review_prompts.py",
    "art_pipeline/vision_reviewer.py",
    "art_pipeline/qa.py",
    "art_pipeline/png_content_qa.py",
)

PAGE_AUTHORITY_FIELDS = (
    "page_id",
    "monster_name",
    "habitat",
    "monster_spec_id",
    "archetype",
    "environment_profile_id",
    "environment_variant",
    "physicality",
    "moment",
    "identity_rules",
    "must_include",
    "must_avoid",
    "coloring_rules",
    "reference_image",
    "modify",
    "composition",
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_file(digest, root: Path, relative: str) -> None:
    path = root / relative
    if not path.exists() or not path.is_file():
        digest.update(f"MISSING:{relative}\n".encode("utf-8"))
        return
    digest.update(relative.replace("\\", "/").encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")


def _hash_json_payload(digest, label: str, payload) -> None:
    digest.update(label.encode("utf-8"))
    digest.update(b"\0")
    digest.update(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )
    digest.update(b"\0")


def _generation_stack_payload(root: Path) -> dict:
    path = root / "config" / "local_ai_stack.json"
    if not path.exists():
        return {"missing": True}
    payload = _read_json(path)
    return {
        "model": payload.get("model"),
        "templates": payload.get("templates"),
        "models": payload.get("models"),
    }


def _review_stack_payload(root: Path) -> dict:
    path = root / "config" / "local_ai_stack.json"
    if not path.exists():
        return {"missing": True}
    payload = _read_json(path)
    return {"vision_reviewer": payload.get("vision_reviewer")}


def _page_authority_payload(page: dict) -> dict:
    return {key: page.get(key) for key in PAGE_AUTHORITY_FIELDS}


def _resolved_candidate_prompts(page: dict, root: Path) -> list[str]:
    # Import lazily to keep the fingerprint module lightweight and avoid
    # module-order coupling during catalog/test imports.
    try:
        from .prompt_builder import build_prompt
    except ImportError:
        from prompt_builder import build_prompt

    # Candidate composition policy currently exposes four canonical variants.
    # Hash all four so changes to any production composition invalidate only
    # pages whose resolved prompt text actually changes.
    return [
        build_prompt(page, candidate_no=candidate_no)
        for candidate_no in range(1, 5)
    ]


def page_generation_fingerprint(page: dict, root: Path = ROOT) -> str:
    """Hash resolved pixel authority, not incidental prompt-source file bytes."""
    digest = hashlib.sha256()
    digest.update(b"BLACKINK_GENERATION_FINGERPRINT_V2\0")

    for relative in GENERATION_EXECUTION_FILES:
        _hash_file(digest, root, relative)
    _hash_json_payload(digest, "GENERATION_STACK", _generation_stack_payload(root))

    _hash_json_payload(
        digest,
        "PAGE_AUTHORITY",
        _page_authority_payload(page),
    )
    _hash_json_payload(
        digest,
        "RESOLVED_CANDIDATE_PROMPTS",
        _resolved_candidate_prompts(page, root),
    )

    reference = str(page.get("reference_image") or "").strip()
    if reference:
        ref_path = Path(reference)
        if not ref_path.is_absolute():
            ref_path = root / reference
        if ref_path.exists() and ref_path.is_file():
            digest.update(b"REFERENCE_IMAGE\0")
            digest.update(ref_path.read_bytes())
            digest.update(b"\0")
        else:
            digest.update(f"MISSING_REFERENCE:{reference}\0".encode("utf-8"))

    return digest.hexdigest()


def page_review_fingerprint(page: dict, root: Path = ROOT) -> str:
    """Hash reviewer/QA authority separately so review changes do not imply rerender."""
    digest = hashlib.sha256()
    digest.update(page_generation_fingerprint(page, root).encode("ascii"))
    digest.update(b"\0")
    for relative in REVIEW_AUTHORITY_FILES:
        _hash_file(digest, root, relative)
    _hash_json_payload(digest, "REVIEW_STACK", _review_stack_payload(root))
    return digest.hexdigest()
