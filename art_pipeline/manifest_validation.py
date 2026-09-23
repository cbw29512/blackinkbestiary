from __future__ import annotations

import math
from pathlib import Path

try:
    from .quality_system import archetype_rules
    from .environment_catalog import environment_fingerprint
    from .manifest_page_validation import (
        validate_environment_dependencies,
        validate_monster_dependencies,
        validate_physicality_dependencies,
    )
    from .page_contract import load_page_contract, missing_required_paths, page_uniqueness_fingerprint, resolve_page_spec
    from .page_recipe_policy import page_recipe_errors
    from .physicality_prompt import locomotion_errors
    from .story_prompt import story_errors
except ImportError:
    from quality_system import archetype_rules
    from environment_catalog import environment_fingerprint
    from manifest_page_validation import (
        validate_environment_dependencies,
        validate_monster_dependencies,
        validate_physicality_dependencies,
    )
    from page_contract import load_page_contract, missing_required_paths, page_uniqueness_fingerprint, resolve_page_spec
    from page_recipe_policy import page_recipe_errors
    from physicality_prompt import locomotion_errors
    from story_prompt import story_errors


REQUIRED_PAGE_FIELDS = {"page_id", "order", "monster_spec_id", "moment", "archetype"}
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
    profile_counts: dict[str, int] = {}
    consecutive_profile = None
    consecutive_count = 0
    max_consecutive_seen: dict[str, int] = {}

    for page in pages:
        page_id = str(page.get("page_id") or "").strip() or "<missing>"
        missing = sorted(REQUIRED_PAGE_FIELDS.difference(page))
        missing_paths = missing_required_paths(page, root)
        if missing:
            errors.append(f"{page_id}: missing fields: {', '.join(missing)}")
        if missing_paths:
            errors.append(f"{page_id}: missing contract fields: {', '.join(missing_paths)}")
        errors.extend(page_recipe_errors(page, root))
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

        errors.extend(validate_monster_dependencies(root, monster_dir, page))
        errors.extend(validate_environment_dependencies(page))
        errors.extend(validate_physicality_dependencies(page))
        errors.extend(story_errors(page, root))
        try:
            resolved = resolve_page_spec(page, root)
            if not str(resolved.get("monster_name") or "").strip():
                errors.append(f"{page_id}: monster_name could not be derived")
            if not str(resolved.get("habitat") or "").strip():
                errors.append(f"{page_id}: habitat could not be derived")
            if not resolved.get("must_avoid"):
                errors.append(f"{page_id}: resolved must_avoid cannot be empty")
            errors.extend(locomotion_errors(resolved))
        except RuntimeError as exc:
            errors.append(f"{page_id}: page contract resolution failed: {exc}")

        profile_id = str(page.get("environment_profile_id") or "").strip()
        profile_counts[profile_id] = profile_counts.get(profile_id, 0) + 1
        if profile_id == consecutive_profile:
            consecutive_count += 1
        else:
            consecutive_profile = profile_id
            consecutive_count = 1
        max_consecutive_seen[profile_id] = max(
            max_consecutive_seen.get(profile_id, 0),
            consecutive_count,
        )

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

    diversity = (load_page_contract(root / "config" / "universal_page_contract.json").get("environment_diversity") or {})
    share = float(diversity.get("max_profile_share", 1.0))
    minimum = int(diversity.get("minimum_repeat_allowance", 1))
    max_consecutive = int(diversity.get("max_consecutive_same_profile", len(pages) or 1))
    max_occurrences = max(minimum, math.ceil((len(pages) or 1) * share))
    for profile_id, count in sorted(profile_counts.items()):
        if count > max_occurrences:
            errors.append(
                f"environment profile {profile_id!r} used {count} times; maximum is {max_occurrences}"
            )
        if max_consecutive_seen.get(profile_id, 0) > max_consecutive:
            errors.append(
                f"environment profile {profile_id!r} repeats more than {max_consecutive} consecutive pages"
            )
    return errors
