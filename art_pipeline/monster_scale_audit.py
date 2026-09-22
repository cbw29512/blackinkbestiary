from __future__ import annotations

import json
import re
from pathlib import Path

try:
    from .monster_catalog import family_profile_path, minimal_recipe_errors
except ImportError:
    from monster_catalog import family_profile_path, minimal_recipe_errors

SCENERY_TERMS = re.compile(
    r"\b(wall|floor|ceiling|torch|sconce|corridor|hallway|room|chamber|altar|"
    r"shrine|trap|furniture|table|chair|reef|tomb|crypt|dungeon|ruin|lair|"
    r"background|scenery)\b",
    re.IGNORECASE,
)

FAMILY_OWNED_KEYS = {
    "family",
    "size",
    "creature_type",
    "visual_identity",
    "accuracy_checks",
    "known_failure_modes",
    "default_habitats",
    "scene_identity",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _scenery_leaks(spec: dict) -> list[str]:
    allowed_sections = {
        "environment_compatibility",
        "reference",
    }
    leaks = []
    for key, value in spec.items():
        if key in allowed_sections:
            continue
        text = json.dumps(value, ensure_ascii=False)
        hits = sorted({item.lower() for item in SCENERY_TERMS.findall(text)})
        if hits:
            leaks.append(f"{key}: {', '.join(hits)}")
    return leaks


def audit_monster_scale(root: Path) -> dict:
    monster_dir = root / "data" / "monsters"
    family_dir = root / "data" / "monster_families"

    counts = {"schema_v1": 0, "schema_v2": 0, "schema_v3_plus": 0}
    migration = []
    strict_errors = []
    family_missing = []
    embedded_identity = []
    scenery_leaks = []
    total = 0

    for path in sorted(monster_dir.glob("*.json")):
        total += 1
        spec = _read(path)
        version = int(spec.get("schema_version") or 1)
        if version >= 3:
            counts["schema_v3_plus"] += 1
            strict_errors.extend(minimal_recipe_errors(path.stem, monster_dir, family_dir))
        elif version == 2:
            counts["schema_v2"] += 1
            migration.append(f"{path.stem}: schema v2")
        else:
            counts["schema_v1"] += 1
            migration.append(f"{path.stem}: schema v1")

        if not family_profile_path(spec, family_dir):
            family_missing.append(path.stem)
            migration.append(f"{path.stem}: missing family_profile")

        if "visual_identity" in spec:
            embedded_identity.append(path.stem)
            migration.append(f"{path.stem}: embeds family-owned visual_identity")

        owned = sorted(FAMILY_OWNED_KEYS.intersection(spec))
        if version >= 3 and owned:
            strict_errors.append(
                f"{path.stem}: schema-v3 recipe contains family-owned keys: {', '.join(owned)}"
            )

        leaks = _scenery_leaks(spec)
        if version >= 3 and leaks:
            scenery_leaks.append({"monster_id": path.stem, "leaks": leaks})
            strict_errors.append(
                f"{path.stem}: schema-v3 recipe contains reusable scenery prose"
            )

    minimal = counts["schema_v3_plus"]
    return {
        "pass": not strict_errors,
        "scale_ready": not strict_errors and minimal == total and not family_missing,
        "monster_specs": total,
        "minimal_recipes": minimal,
        "legacy_recipes": total - minimal,
        "schema_counts": counts,
        "family_profile_coverage": total - len(family_missing),
        "missing_family_profiles": family_missing,
        "embedded_visual_identity": embedded_identity,
        "scenery_leaks": scenery_leaks,
        "migration_debt": list(dict.fromkeys(migration)),
        "errors": strict_errors,
    }
