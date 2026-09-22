from __future__ import annotations

from pathlib import Path

from quality_system import archetype_rules


REQUIRED_PAGE_FIELDS = {
    "page_id",
    "order",
    "monster_name",
    "habitat",
    "moment",
    "must_include",
    "must_avoid",
    "monster_spec_id",
    "archetype",
}


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

        if not page.get("must_include"):
            errors.append(f"{page_id}: must_include cannot be empty")
        if not page.get("must_avoid"):
            errors.append(f"{page_id}: must_avoid cannot be empty")

        archetype = str(page.get("archetype") or "")
        if archetype not in archetypes:
            errors.append(f"{page_id}: unknown archetype {archetype!r}")

        spec_id = str(page.get("monster_spec_id") or "").strip()
        spec_path = monster_dir / f"{spec_id}.json"
        if not spec_id or not spec_path.exists():
            errors.append(f"{page_id}: canonical monster spec missing: {spec_id}")

    if seen_orders and seen_orders != set(range(1, len(pages) + 1)):
        errors.append("page order must be contiguous starting at 1")
    return errors
