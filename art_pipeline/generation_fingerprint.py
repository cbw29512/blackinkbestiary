from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GENERATION_AUTHORITY_FILES = (
    "config/universal_monster_contract.json",
    "config/universal_environment_contract.json",
    "config/universal_page_contract.json",
    "config/universal_story_contract.json",
    "config/coloring_page_standard.json",
    "config/environment_standard.json",
    "config/page_archetypes.json",
    "config/kdp_print_standard.json",
    "data/environment_overlays.json",
    "data/environment_spatial_envelopes.json",
    "data/environment_variation_families.json",
    "art_pipeline/prompt_builder.py",
    "art_pipeline/monster_catalog.py",
    "art_pipeline/environment_catalog.py",
    "art_pipeline/environment_components.py",
    "art_pipeline/environment_assembly.py",
    "art_pipeline/environment_prompt.py",
    "art_pipeline/environment_spatial.py",
    "art_pipeline/physicality_prompt.py",
    "art_pipeline/story_prompt.py",
    "art_pipeline/style_rules.py",
    "art_pipeline/page_contract.py",
    "art_pipeline/edit_prompt.py",
    "art_pipeline/flux2_klein_profile.py",
    "art_pipeline/image_edit_profile.py",
    "art_pipeline/generation_runtime.py",
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


def page_generation_fingerprint(page: dict, root: Path = ROOT) -> str:
    """Hash only authority that can materially change rendered candidate pixels."""
    digest = hashlib.sha256()
    for relative in GENERATION_AUTHORITY_FILES:
        _hash_file(digest, root, relative)
    _hash_json_payload(digest, "GENERATION_STACK", _generation_stack_payload(root))

    spec_id = str(page.get("monster_spec_id") or "").strip()
    if spec_id:
        monster_rel = f"data/monsters/{spec_id}.json"
        _hash_file(digest, root, monster_rel)
        monster_path = root / monster_rel
        if monster_path.exists():
            monster = _read_json(monster_path)
            family = str(monster.get("family_profile") or monster.get("family") or "").strip()
            if family:
                _hash_file(digest, root, f"data/monster_families/{family}.json")

    environment_id = str(page.get("environment_profile_id") or "").strip()
    environment_family = environment_id.split(".", 1)[0] if "." in environment_id else ""
    if environment_family:
        _hash_file(digest, root, f"data/environment_families/{environment_family}.json")
        _hash_file(digest, root, f"data/environment_components/{environment_family}.json")

    payload = json.dumps(
        _page_authority_payload(page),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    digest.update(b"PAGE\0")
    digest.update(payload)
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
