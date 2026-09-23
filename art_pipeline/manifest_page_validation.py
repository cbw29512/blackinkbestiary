from __future__ import annotations

from pathlib import Path

try:
    from .environment_catalog import environment_identity_errors, resolve_environment_profile
    from .monster_catalog import minimal_recipe_errors, resolve_monster_spec
    from .source_scope import source_scope_errors
except ImportError:
    from environment_catalog import environment_identity_errors, resolve_environment_profile
    from monster_catalog import minimal_recipe_errors, resolve_monster_spec
    from source_scope import source_scope_errors


REQUIRED_VISUAL_FIELDS = {
    "core_identity",
    "silhouette",
    "head_features",
    "body_shape",
    "surface",
    "signature_gear",
    "attitude",
    "must_keep",
    "must_avoid",
}


def validate_monster_dependencies(root: Path, monster_dir: Path, page: dict) -> list[str]:
    page_id = page["page_id"]
    spec_id = str(page.get("monster_spec_id") or "").strip()
    if not spec_id:
        return [f"{page_id}: canonical monster spec missing"]
    try:
        spec = resolve_monster_spec(spec_id, monster_dir)
    except RuntimeError as exc:
        return [f"{page_id}: {exc}"]

    errors: list[str] = []
    errors.extend(minimal_recipe_errors(spec_id, monster_dir))
    errors.extend(source_scope_errors(spec_id, root))
    visual = spec.get("visual_identity") or {}
    missing = sorted(REQUIRED_VISUAL_FIELDS.difference(visual))
    if missing:
        errors.append(f"{page_id}: monster spec missing visual fields: {', '.join(missing)}")
    if not visual.get("must_keep"):
        errors.append(f"{page_id}: monster spec must_keep cannot be empty")
    if not visual.get("must_avoid"):
        errors.append(f"{page_id}: monster spec must_avoid cannot be empty")
    if not spec.get("accuracy_checks"):
        errors.append(f"{page_id}: monster spec accuracy_checks cannot be empty")
    return errors


def validate_environment_dependencies(page: dict) -> list[str]:
    page_id = page["page_id"]
    errors: list[str] = []
    profile_id = str(page.get("environment_profile_id") or "").strip()
    try:
        profile = resolve_environment_profile(profile_id)
        errors.extend(f"{page_id}: {item}" for item in environment_identity_errors(profile))
    except RuntimeError as exc:
        errors.append(f"{page_id}: {exc}")

    variant = page.get("environment_variant") or {}
    for field in ("landmark", "framing", "interaction"):
        if not str(variant.get(field) or "").strip():
            errors.append(f"{page_id}: environment_variant.{field} is required")
    return errors


def validate_physicality_dependencies(page: dict) -> list[str]:
    page_id = page["page_id"]
    physicality = page.get("physicality") or {}
    errors: list[str] = []
    for field in ("mode", "support", "motion"):
        if not str(physicality.get(field) or "").strip():
            errors.append(f"{page_id}: physicality.{field} is required")
    return errors
