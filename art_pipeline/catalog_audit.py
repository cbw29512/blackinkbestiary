from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REQUIRED_VISUAL = {
    "core_identity",
    "silhouette",
    "head_features",
    "body_shape",
    "surface",
    "must_keep",
    "must_avoid",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_monster_catalog(root: Path) -> dict:
    monster_dir = root / "data" / "monsters"
    family_dir = root / "data" / "monster_families"
    specs = []
    groups: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    errors: list[str] = []

    for path in sorted(monster_dir.glob("*.json")):
        try:
            spec = _read(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue
        specs.append((path, spec))
        family = str(spec.get("family") or "").strip()
        if family:
            groups[family].append((path, spec))

        profile_id = str(spec.get("family_profile") or "").strip()
        if profile_id:
            profile_path = family_dir / f"{profile_id}.json"
            if not profile_path.exists():
                errors.append(f"{path.name}: family_profile {profile_id!r} does not exist")

    repeated = {family: items for family, items in groups.items() if len(items) >= 2}
    for family, items in sorted(repeated.items()):
        for path, spec in items:
            profile_id = str(spec.get("family_profile") or "").strip()
            if not profile_id:
                errors.append(
                    f"{path.name}: repeated family {family!r} requires family_profile"
                )

    family_profiles = 0
    for path in sorted(family_dir.glob("*.json")):
        family_profiles += 1
        try:
            profile = _read(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: invalid family JSON: {exc}")
            continue
        if profile.get("profile_id") != path.stem:
            errors.append(f"{path.name}: profile_id must match filename")
        visual = profile.get("visual_identity") or {}
        missing = sorted(REQUIRED_VISUAL.difference(visual))
        if missing:
            errors.append(f"{path.name}: missing visual fields: {', '.join(missing)}")
        if not profile.get("accuracy_checks"):
            errors.append(f"{path.name}: accuracy_checks cannot be empty")
        if not profile.get("known_failure_modes"):
            errors.append(f"{path.name}: known_failure_modes cannot be empty")

    return {
        "pass": not errors,
        "monster_specs": len(specs),
        "repeated_families": sorted(repeated),
        "family_profiles": family_profiles,
        "errors": errors,
    }
