from __future__ import annotations

from pathlib import Path

try:
    from .quality_system import archetype_rules
    from .monster_catalog import resolve_monster_spec
    from .environment_catalog import environment_fingerprint, resolve_environment_profile
except ImportError:
    from quality_system import archetype_rules
    from monster_catalog import resolve_monster_spec
    from environment_catalog import environment_fingerprint, resolve_environment_profile


REQUIRED_PAGE_FIELDS = {
    "page_id", "order", "monster_name", "habitat", "moment",
    "must_include", "must_avoid", "monster_spec_id", "archetype",
    "environment_profile_id", "environment_variant",
}
REQUIRED_VISUAL_FIELDS = {
    "core_identity", "silhouette", "head_features", "body_shape", "surface",
    "signature_gear", "attitude", "must_keep", "must_avoid",
}


def _validate_spec(monster_dir: Path, page: dict) -> list[str]:
    page_id = page["page_id"]
    spec_id = str(page.get("monster_spec_id") or "").strip()
    if not spec_id:
        return [f"{page_id}: canonical monster spec missing"]
    try:
        spec = resolve_monster_spec(spec_id, monster_dir)
    except RuntimeError as exc:
        return [f"{page_id}: {exc}"]

    errors = []
    if spec.get("monster_name") != page.get("monster_name"):
        errors.append(f"{page_id}: monster spec name mismatch")
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

def _validate_environment(page: dict) -> list[str]:
    page_id = page["page_id"]
    errors = []
    profile_id = str(page.get("environment_profile_id") or "").strip()
    try:
        resolve_environment_profile(profile_id)
    except RuntimeError as exc:
        errors.append(f"{page_id}: {exc}")

    variant = page.get("environment_variant") or {}
    for field in ("landmark", "framing", "interaction"):
        if not str(variant.get(field) or "").strip():
            errors.append(f"{page_id}: environment_variant.{field} is required")
    return errors

def validate_manifest(root: Path, tome: dict, monster_dir: Path) -> list[str]:
    errors: list[str] = []
    pages = tome.get("pages") or []
    expected = tome.get("total_pages")
    if not isinstance(expected, int) or expected <= 0:
        errors.append("total_pages must be a positive integer")
    if expected != len(pages):
        errors.append("manifest page count does not match total_pages")

    archetypes = archetype_rules(root)
    seen_ids: set[str] = set()
    seen_orders: set[int] = set()
    seen_backgrounds: dict[str, str] = {}

    for page in pages:
        page_id = str(page.get("page_id") or "").strip() or "<missing>"
        missing = sorted(REQUIRED_PAGE_FIELDS.difference(page))
        if missing:
            errors.append(f"{page_id}: missing fields: {', '.join(missing)}")
            continue

        if page_id in seen_ids:
            errors.append(f"{page_id}: duplicate page_id")
        seen_ids.add(page_id)

        order = page.get("order")
        if not isinstance(order, int) or order <= 0:
            errors.append(f"{page_id}: order must be a positive integer")
        elif order in seen_orders:
            errors.append(f"{page_id}: duplicate order {order}")
        seen_orders.add(order)

        if not str(page.get("habitat") or "").strip():
            errors.append(f"{page_id}: habitat cannot be empty")
        if not str(page.get("moment") or "").strip():
            errors.append(f"{page_id}: moment cannot be empty")
        if not page.get("must_include"):
            errors.append(f"{page_id}: must_include cannot be empty")
        if not page.get("must_avoid"):
            errors.append(f"{page_id}: must_avoid cannot be empty")

        archetype = str(page.get("archetype") or "")
        if archetype not in archetypes:
            errors.append(f"{page_id}: unknown archetype {archetype!r}")

        errors.extend(_validate_spec(monster_dir, page))
        errors.extend(_validate_environment(page))
        fingerprint = environment_fingerprint(page)
        if fingerprint in seen_backgrounds:
            errors.append(f"{page_id}: background duplicates {seen_backgrounds[fingerprint]}")
        else:
            seen_backgrounds[fingerprint] = page_id

    if seen_orders and seen_orders != set(range(1, len(pages) + 1)):
        errors.append("page order must be contiguous starting at 1")
    return errors
