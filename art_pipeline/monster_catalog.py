from __future__ import annotations

import json
from pathlib import Path

try:
    from .monster_profile_catalog import IDENTITY_DIR, merge_dict, resolve_profile_layers
    from .monster_resolution import apply_defaults, apply_recipe, decorate_resolved
except ImportError:
    from monster_profile_catalog import IDENTITY_DIR, merge_dict, resolve_profile_layers
    from monster_resolution import apply_defaults, apply_recipe, decorate_resolved

ROOT = Path(__file__).resolve().parents[1]
MONSTER_DIR = ROOT / "data" / "monsters"
FAMILY_DIR = ROOT / "data" / "monster_families"
CONTRACT_FILE = ROOT / "config" / "universal_monster_contract.json"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load creature catalog file {path}: {exc}") from exc


def load_monster_contract(path: Path = CONTRACT_FILE) -> dict:
    return _read_json(path)


def resolve_monster_spec(
    spec_id: str,
    monster_dir: Path = MONSTER_DIR,
    family_dir: Path = FAMILY_DIR,
    identity_dir: Path = IDENTITY_DIR,
) -> dict:
    spec_id = str(spec_id or "").strip()
    if not spec_id:
        raise RuntimeError("Monster spec ID is required")
    path = monster_dir / f"{spec_id}.json"
    if not path.exists():
        raise RuntimeError(f"Monster spec not found: {path}")

    raw = _read_json(path)
    if raw.get("monster_id") != spec_id:
        raise RuntimeError(f"Monster spec ID mismatch in {path}")

    contract = load_monster_contract(ROOT / "config" / "universal_monster_contract.json")
    layers = resolve_profile_layers(raw, family_dir, identity_dir)
    resolved = merge_dict(layers["base"], raw)
    resolved = apply_defaults(resolved, contract)
    resolved = apply_recipe(resolved, raw)
    resolved = decorate_resolved(resolved, raw, layers, contract)
    resolved["catalog"] = {
        "monster_file": path.relative_to(ROOT).as_posix(),
        "family_profile": layers["family_path"].relative_to(ROOT).as_posix()
        if layers["family_path"] else None,
        "identity_profile": layers["identity_path"].relative_to(ROOT).as_posix()
        if layers["identity_path"] else None,
        "family_profile_id": layers["family_id"],
        "identity_profile_id": layers["identity_id"],
        "minimal_recipe": not bool(raw.get("visual_identity")),
    }
    return resolved


def minimal_recipe_errors(
    spec_id: str,
    monster_dir: Path = MONSTER_DIR,
    family_dir: Path = FAMILY_DIR,
    identity_dir: Path = IDENTITY_DIR,
) -> list[str]:
    path = monster_dir / f"{spec_id}.json"
    if not path.exists():
        return [f"Monster spec not found: {path}"]
    raw = _read_json(path)
    schema = int(raw.get("schema_version") or 1)
    if schema < 3:
        return []

    contract = load_monster_contract(ROOT / "config" / "universal_monster_contract.json")
    errors = []
    required = (
        contract.get("v4_recipe_required")
        if schema >= 4
        else contract.get("minimal_recipe_required")
    ) or []
    for field in required:
        if not str(raw.get(field) or "").strip():
            errors.append(f"{spec_id}: minimal monster recipe missing {field}")

    if schema >= 4:
        forbidden = set(contract.get("v4_recipe_forbidden_fields") or [])
        present = sorted(field for field in forbidden if field in raw)
        if present:
            errors.append(f"{spec_id}: v4 recipe contains identity fields: {', '.join(present)}")
    try:
        resolve_profile_layers(raw, family_dir, identity_dir)
    except RuntimeError as exc:
        errors.append(f"{spec_id}: {exc}")
    return errors


def load_monster_for_page(page: dict) -> dict | None:
    spec_id = str(page.get("monster_spec_id") or "").strip()
    return resolve_monster_spec(spec_id) if spec_id else None
