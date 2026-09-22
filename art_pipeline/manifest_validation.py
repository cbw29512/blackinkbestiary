from __future__ import annotations

from pathlib import Path

try:
    from .quality_system import archetype_rules
    from .monster_catalog import resolve_monster_spec
    from .environment_catalog import environment_fingerprint, resolve_environment_profile
    from .page_contract import missing_required_paths, page_uniqueness_fingerprint, resolve_page_spec
except ImportError:
    from quality_system import archetype_rules
    from monster_catalog import resolve_monster_spec
    from environment_catalog import environment_fingerprint, resolve_environment_profile
    from page_contract import missing_required_paths, page_uniqueness_fingerprint, resolve_page_spec


REQUIRED_PAGE_FIELDS = {"page_id", "order", "monster_spec_id", "moment", "archetype"}
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
    explicit_name = str(page.get("monster_name") or "").strip()
    if explicit_name and spec.get("monster_name") != explicit_name:
        errors.append(f"{page_id}: explicit monster_name conflicts with catalog")
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

def _validate_physicality(page: dict) -> list[str]:
    page_id = page["page_id"]
    physicality = page.get("physicality") or {}
    errors = []
    for field in ("mode", "support", "motion"):
        if not str(physicality.get(field) or "").strip():
            errors.append(f"{page_id}: physicality.{field} is required")
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
    seen_pages: dict[str, str] = {}

    for page in pages:
        page_id = str(page.get("page_id") or "").strip() or "<missing>"
        missing = sorted(REQUIRED_PAGE_FIELDS.difference(page))
        missing_paths = missing_required_paths(page, root)
        if missing:
            errors.append(f"{page_id}: missing fields: {', '.join(missing)}")
        if missing_paths:
            errors.append(f"{page_id}: missing contract fields: {', '.join(missing_paths)}")
        if missing or missing_paths:
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

        if not str(page.get("moment") or "").strip():
            errors.append(f"{page_id}: moment cannot be empty")

        archetype = str(page.get("archetype") or "")
        if archetype not in archetypes:
            errors.append(f"{page_id}: unknown archetype {archetype!r}")

        errors.extend(_validate_spec(monster_dir, page))
        errors.extend(_validate_environment(page))
        errors.extend(_validate_physicality(page))
        try:
            resolved = resolve_page_spec(page, root)
            if not str(resolved.get("monster_name") or "").strip():
                errors.append(f"{page_id}: monster_name could not be derived")
            if not str(resolved.get("habitat") or "").strip():
                errors.append(f"{page_id}: habitat could not be derived")
            if not resolved.get("must_avoid"):
                errors.append(f"{page_id}: resolved must_avoid cannot be empty")
        except RuntimeError as exc:
            errors.append(f"{page_id}: page contract resolution failed: {exc}")

        fingerprint = environment_fingerprint(page)
        if fingerprint in seen_backgrounds:
            errors.append(f"{page_id}: background duplicates {seen_backgrounds[fingerprint]}")
        else:
            seen_backgrounds[fingerprint] = page_id

        try:
            page_fingerprint = page_uniqueness_fingerprint(page, root)
        except RuntimeError:
            page_fingerprint = ""
        if page_fingerprint:
            if page_fingerprint in seen_pages:
                errors.append(f"{page_id}: full page recipe duplicates {seen_pages[page_fingerprint]}")
            else:
                seen_pages[page_fingerprint] = page_id

    if seen_orders and seen_orders != set(range(1, len(pages) + 1)):
        errors.append("page order must be contiguous starting at 1")
    return errors
