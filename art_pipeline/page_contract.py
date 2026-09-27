from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

try:
    from .environment_catalog import resolve_environment_profile
    from .monster_catalog import resolve_monster_spec
except ImportError:
    from environment_catalog import resolve_environment_profile
    from monster_catalog import resolve_monster_spec

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILE = ROOT / "config" / "universal_page_contract.json"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load page contract {path}: {exc}") from exc


def load_page_contract(path: Path = CONTRACT_FILE) -> dict:
    return _read_json(path)


def _merge_unique(*groups) -> list:
    result = []
    for group in groups:
        for item in group or []:
            if item not in result:
                result.append(item)
    return result


def _merge_dict(base: dict, override: dict | None) -> dict:
    merged = deepcopy(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def resolve_page_spec(page: dict, root: Path = ROOT) -> dict:
    contract = load_page_contract(root / "config" / "universal_page_contract.json")
    resolved = deepcopy(page)

    monster = resolve_monster_spec(
        page.get("monster_spec_id"),
        root / "data" / "monsters",
        root / "data" / "monster_families",
    )
    environment = resolve_environment_profile(
        page.get("environment_profile_id"),
        root / "data" / "environment_families",
    )
    visual = monster.get("visual_identity") or {}

    resolved["monster_name"] = monster.get("monster_name")
    resolved["habitat"] = environment.get("name")
    monster_size = str(monster.get("size") or "").strip().lower()
    subject_scale_rules = contract.get("subject_scale_rules") or {}
    resolved["subject_scale_rule"] = (
        subject_scale_rules.get(monster_size)
        or subject_scale_rules.get("default")
        or ""
    )
    resolved["identity_rules"] = _merge_unique(
        monster.get("accuracy_checks"),
        page.get("identity_rules"),
    )
    resolved["must_avoid"] = _merge_unique(
        contract.get("global_must_avoid"),
        visual.get("must_avoid"),
        environment.get("must_avoid"),
        page.get("must_avoid"),
    )
    defaults = contract.get("defaults") or {}
    resolved.setdefault("composition", defaults.get("composition", ""))
    resolved["coloring_rules"] = _merge_dict(
        defaults.get("coloring_rules") or {},
        page.get("coloring_rules"),
    )
    locomotion_defaults = {
        "can_fly": bool((contract.get("locomotion") or {}).get("default_can_fly", False))
    }
    resolved["locomotion"] = _merge_dict(
        locomotion_defaults,
        monster.get("locomotion") or {},
    )
    resolved["_resolved"] = {
        "contract_id": contract.get("contract_id"),
        "monster_identity_version": monster.get("identity_version"),
        "monster_size": monster_size,
        "monster_family_profile": (monster.get("catalog") or {}).get("family_profile"),
        "environment_profile": environment.get("environment_id"),
        "environment_family": environment.get("environment_family"),
    }
    return resolved


def contract_required_paths(root: Path = ROOT) -> list[str]:
    contract = load_page_contract(root / "config" / "universal_page_contract.json")
    return list(contract.get("required_unique_fields") or [])


def missing_required_paths(page: dict, root: Path = ROOT) -> list[str]:
    missing = []
    for dotted in contract_required_paths(root):
        value = page
        for part in dotted.split("."):
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(dotted)
    return missing


def resolve_manifest(tome: dict, root: Path = ROOT) -> dict:
    resolved = deepcopy(tome)
    resolved["pages"] = [resolve_page_spec(page, root) for page in tome.get("pages", [])]
    resolved["page_contract"] = load_page_contract(
        root / "config" / "universal_page_contract.json"
    ).get("contract_id")
    return resolved


def page_uniqueness_fingerprint(page: dict, root: Path = ROOT) -> str:
    resolved = resolve_page_spec(page, root)
    variant = resolved.get("environment_variant") or {}
    physicality = resolved.get("physicality") or {}
    values = [
        resolved.get("monster_spec_id"),
        resolved.get("environment_profile_id"),
        variant.get("landmark"),
        variant.get("framing"),
        variant.get("interaction"),
        resolved.get("moment"),
        physicality.get("mode"),
    ]
    return "|".join(
        " ".join(str(value or "").strip().lower().split())
        for value in values
    )
