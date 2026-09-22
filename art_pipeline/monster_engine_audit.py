from __future__ import annotations

import json
from pathlib import Path

try:
    from .monster_catalog import resolve_monster_spec
    from .monster_profile_catalog import resolved_profile_errors
except ImportError:
    from monster_catalog import resolve_monster_spec
    from monster_profile_catalog import resolved_profile_errors

SCENE_LEAK_TERMS = (
    "pillar orbit",
    "motion around pillar",
    "pedestal origin",
    "suspended key",
    "victim being wrapped",
    "two halves move upward",
    "bars interact with ooze",
    "dragon skull",
    "coin offerings",
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _identity_text(raw: dict) -> str:
    visual = raw.get("visual_identity") or {}
    values = []
    for key in ("core_identity", "silhouette", "head_features", "body_shape", "limb_structure"):
        values.append(str(visual.get(key) or ""))
    values.extend(str(item) for item in visual.get("must_keep") or [])
    values.extend(str(item) for item in raw.get("accuracy_checks") or [])
    return " ".join(values).lower()


def audit_monster_engine(root: Path) -> dict:
    monster_dir = root / "data" / "monsters"
    identity_dir = root / "data" / "monster_identity_profiles"
    family_dir = root / "data" / "monster_families"
    errors, protection_gaps, scene_leaks = [], [], []
    schema_counts: dict[int, int] = {}
    full_identity, v4_minimal, oversized = [], [], []
    render_unspecified, anatomy_unspecified = [], []

    for path in sorted(monster_dir.glob("*.json")):
        try:
            raw = _read(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue
        schema = int(raw.get("schema_version") or 1)
        schema_counts[schema] = schema_counts.get(schema, 0) + 1
        if raw.get("visual_identity"):
            full_identity.append(path.stem)
        if schema >= 4 and not raw.get("visual_identity"):
            v4_minimal.append(path.stem)
        if len(path.read_bytes()) > 900:
            oversized.append(path.stem)

        try:
            resolved = resolve_monster_spec(
                path.stem,
                monster_dir,
                family_dir,
                identity_dir,
            )
        except RuntimeError as exc:
            errors.append(f"{path.name}: {exc}")
            continue

        gaps = resolved_profile_errors(resolved)
        if gaps:
            protection_gaps.append({"monster_id": path.stem, "missing": gaps})
        render = resolved.get("render_identity") or {}
        anatomy = resolved.get("anatomy") or {}
        if render.get("subject_mode") in (None, "", "unspecified"):
            render_unspecified.append(path.stem)
        if anatomy.get("body_plan") in (None, "", "unspecified"):
            anatomy_unspecified.append(path.stem)

        leak_text = _identity_text(raw)
        matches = [term for term in SCENE_LEAK_TERMS if term in leak_text]
        if matches:
            scene_leaks.append({"monster_id": path.stem, "terms": matches})

    identity_profiles = list(identity_dir.glob("*.json")) if identity_dir.exists() else []
    legacy_count = sum(
        count for schema, count in schema_counts.items() if schema < 4
    )
    migration_complete = legacy_count == 0 and not full_identity
    protection_complete = not protection_gaps
    scene_clean = not scene_leaks
    production_identity_ready = (
        not errors and migration_complete and protection_complete and scene_clean
    )
    return {
        "pass": not errors,
        "production_identity_ready": production_identity_ready,
        "migration_complete": migration_complete,
        "monster_specs": sum(schema_counts.values()),
        "schema_counts": schema_counts,
        "family_profiles": len(list(family_dir.glob("*.json"))),
        "identity_profiles": len(identity_profiles),
        "v4_minimal_recipes": len(v4_minimal),
        "full_identity_recipes": len(full_identity),
        "oversized_recipes": len(oversized),
        "protection_gap_count": len(protection_gaps),
        "scene_leak_count": len(scene_leaks),
        "render_mode_unspecified": len(render_unspecified),
        "body_plan_unspecified": len(anatomy_unspecified),
        "migration_debt": {
            "legacy_recipes": legacy_count,
            "full_identity_recipes": full_identity[:20],
            "oversized_recipes": oversized[:20],
            "protection_gaps": protection_gaps[:20],
            "scene_leaks": scene_leaks[:20],
        },
        "errors": errors,
    }
