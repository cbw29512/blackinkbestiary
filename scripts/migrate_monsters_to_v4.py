from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONSTER_DIR = ROOT / "data" / "monsters"
IDENTITY_DIR = ROOT / "data" / "monster_identity_profiles"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _profile_payload(raw: dict) -> dict:
    profile = {
        "schema_version": 1,
        "identity_version": int(raw.get("identity_version") or 1),
        "profile_id": raw["monster_id"],
        "display_name": raw["monster_name"],
    }
    parent = str(raw.get("family_profile") or "").strip()
    if parent:
        profile["extends_family"] = parent
    taxonomy = {
        "family": raw.get("family"),
        "creature_type": raw.get("creature_type"),
        "default_size": raw.get("size"),
    }
    profile["taxonomy"] = {k: v for k, v in taxonomy.items() if v}
    for key in (
        "visual_identity",
        "scene_identity",
        "accuracy_checks",
        "known_failure_modes",
        "locomotion",
        "default_habitats",
        "render_identity",
        "anatomy",
        "reference",
    ):
        if raw.get(key) not in (None, [], {}):
            profile[key] = raw[key]
    return profile


def migrate(monster_id: str, force: bool = False) -> tuple[Path, Path]:
    path = MONSTER_DIR / f"{monster_id}.json"
    if not path.exists():
        raise RuntimeError(f"monster not found: {path}")
    raw = _read(path)
    if int(raw.get("schema_version") or 1) >= 4 and not raw.get("visual_identity"):
        raise RuntimeError(f"{monster_id} is already a schema-v4 minimal recipe")
    if not raw.get("visual_identity"):
        raise RuntimeError(f"{monster_id} has no legacy visual_identity to migrate")

    IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
    profile_path = IDENTITY_DIR / f"{monster_id}.json"
    if profile_path.exists() and not force:
        raise RuntimeError(f"identity profile already exists: {profile_path}")

    profile = _profile_payload(raw)
    recipe = {
        "schema_version": 4,
        "monster_id": raw["monster_id"],
        "monster_name": raw["monster_name"],
        "identity_profile": monster_id,
    }
    if raw.get("variant_traits"):
        recipe["variant_traits"] = raw["variant_traits"]

    profile_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    path.write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")
    return path, profile_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move legacy monster identity into reusable schema-v4 identity profiles."
    )
    parser.add_argument("monster_ids", nargs="*", help="Monster IDs; omit with --all")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    ids = args.monster_ids
    if args.all:
        ids = [path.stem for path in sorted(MONSTER_DIR.glob("*.json"))]
    if not ids:
        print("REFUSED: provide monster IDs or --all")
        return 2

    failures = []
    for monster_id in ids:
        try:
            recipe, profile = migrate(monster_id, args.force)
            print(f"MIGRATED: {monster_id} -> {recipe.name} + {profile.name}")
        except RuntimeError as exc:
            failures.append(f"{monster_id}: {exc}")
            print(f"SKIPPED: {monster_id}: {exc}")

    if failures:
        print(f"Completed with {len(failures)} skipped/failed entries.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
