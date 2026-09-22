from __future__ import annotations

from pathlib import Path

try:
    from .monster_data import (
        CONTRACT_FILE,
        FAMILY_DIR,
        MONSTER_DIR,
        ROOT,
        VARIANT_DIR,
        apply_contract_defaults,
        apply_recipe_overrides,
        family_profile_path,
        merge_dict,
        read_json,
        variant_profile_path,
    )
except ImportError:
    from monster_data import (
        CONTRACT_FILE,
        FAMILY_DIR,
        MONSTER_DIR,
        ROOT,
        VARIANT_DIR,
        apply_contract_defaults,
        apply_recipe_overrides,
        family_profile_path,
        merge_dict,
        read_json,
        variant_profile_path,
    )


def load_monster_contract(path: Path = CONTRACT_FILE) -> dict:
    return read_json(path)


def resolve_monster_spec(
    spec_id: str,
    monster_dir: Path = MONSTER_DIR,
    family_dir: Path = FAMILY_DIR,
    variant_dir: Path = VARIANT_DIR,
) -> dict:
    spec_id = str(spec_id or "").strip()
    if not spec_id:
        raise RuntimeError("Monster spec ID is required")

    path = monster_dir / f"{spec_id}.json"
    if not path.exists():
        raise RuntimeError(f"Monster spec not found: {path}")

    raw = read_json(path)
    if raw.get("monster_id") != spec_id:
        raise RuntimeError(f"Monster spec ID mismatch in {path}")

    contract = load_monster_contract(ROOT / "config" / "universal_monster_contract.json")
    family_path = family_profile_path(raw, family_dir)
    family = read_json(family_path) if family_path else {}
    variant_path = variant_profile_path(raw, variant_dir)
    variant = read_json(variant_path) if variant_path else {}

    if variant and variant.get("family_profile") != raw.get("family_profile"):
        raise RuntimeError(
            f"Variant {raw.get('variant_profile')!r} requires family "
            f"{variant.get('family_profile')!r}, not {raw.get('family_profile')!r}"
        )

    resolved = merge_dict(family, variant)
    resolved = merge_dict(resolved, raw)
    resolved = apply_contract_defaults(resolved, contract)
    resolved = apply_recipe_overrides(resolved, raw)

    taxonomy = family.get("taxonomy") or {}
    resolved["family"] = taxonomy.get("family") or raw.get("family_profile")
    resolved["size"] = (
        raw.get("size")
        or variant.get("size")
        or taxonomy.get("default_size")
        or ""
    )
    resolved["creature_type"] = (
        raw.get("creature_type")
        or variant.get("creature_type")
        or taxonomy.get("creature_type")
        or ""
    )
    resolved["schema_version"] = int(raw.get("schema_version") or 1)
    resolved["identity_version"] = int(
        raw.get("identity_version")
        or variant.get("identity_version")
        or family.get("identity_version")
        or 1
    )
    resolved["monster_contract"] = contract.get("contract_id")
    resolved["catalog"] = {
        "monster_file": path.relative_to(ROOT).as_posix()
        if ROOT in path.resolve().parents else str(path),
        "family_profile": family_path.relative_to(ROOT).as_posix()
        if family_path and ROOT in family_path.resolve().parents else None,
        "variant_profile": variant_path.relative_to(ROOT).as_posix()
        if variant_path and ROOT in variant_path.resolve().parents else None,
        "family_identity_version": family.get("identity_version"),
        "variant_identity_version": variant.get("identity_version"),
        "minimal_recipe": "visual_identity" not in raw,
    }
    return resolved


def minimal_recipe_errors(
    spec_id: str,
    monster_dir: Path = MONSTER_DIR,
    family_dir: Path = FAMILY_DIR,
    variant_dir: Path = VARIANT_DIR,
) -> list[str]:
    path = monster_dir / f"{spec_id}.json"
    if not path.exists():
        return [f"Monster spec not found: {path}"]

    raw = read_json(path)
    contract = load_monster_contract(ROOT / "config" / "universal_monster_contract.json")
    errors = []
    for field in contract.get("minimal_recipe_required") or []:
        if not str(raw.get(field) or "").strip():
            errors.append(f"{spec_id}: minimal monster recipe missing {field}")

    family_path = family_profile_path(raw, family_dir)
    if not family_path:
        errors.append(f"{spec_id}: minimal monster recipe requires a valid family_profile")

    variant_id = str(raw.get("variant_profile") or "").strip()
    if variant_id:
        variant_path = variant_dir / f"{variant_id}.json"
        if not variant_path.exists():
            errors.append(f"{spec_id}: variant_profile {variant_id!r} does not exist")
        else:
            variant = read_json(variant_path)
            if variant.get("family_profile") != raw.get("family_profile"):
                errors.append(
                    f"{spec_id}: variant_profile {variant_id!r} belongs to "
                    f"{variant.get('family_profile')!r}, not {raw.get('family_profile')!r}"
                )
    return errors


def load_monster_for_page(
    page: dict,
    monster_dir: Path = MONSTER_DIR,
    family_dir: Path = FAMILY_DIR,
    variant_dir: Path = VARIANT_DIR,
) -> dict | None:
    spec_id = str(page.get("monster_spec_id") or "").strip()
    if not spec_id:
        return None
    return resolve_monster_spec(spec_id, monster_dir, family_dir, variant_dir)
