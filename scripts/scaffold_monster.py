from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "art_pipeline"))
from source_scope import monster_allowed

ROOT = Path(__file__).resolve().parents[1]
MONSTER_DIR = ROOT / "data" / "monsters"
IDENTITY_DIR = ROOT / "data" / "monster_identity_profiles"
FAMILY_DIR = ROOT / "data" / "monster_families"


def _profile_exists(profile_id: str) -> bool:
    return (
        (IDENTITY_DIR / f"{profile_id}.json").exists()
        or (FAMILY_DIR / f"{profile_id}.json").exists()
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a schema-v4 monster recipe pointing to reusable identity."
    )
    parser.add_argument("monster_id")
    parser.add_argument("monster_name")
    parser.add_argument("identity_profile")
    parser.add_argument("--traits", default="", help="Comma-separated true variant traits")
    args = parser.parse_args()

    if not monster_allowed(args.monster_id, ROOT):
        print(f"REFUSED: {args.monster_id!r} is not on the approved project roster.")
        return 4
    if not _profile_exists(args.identity_profile):
        print(f"REFUSED: unknown identity profile {args.identity_profile!r}")
        return 2

    path = MONSTER_DIR / f"{args.monster_id}.json"
    if path.exists():
        print(f"REFUSED: monster already exists: {path}")
        return 3

    payload = {
        "schema_version": 4,
        "monster_id": args.monster_id,
        "monster_name": args.monster_name,
        "identity_profile": args.identity_profile,
    }
    traits = [item.strip() for item in args.traits.split(",") if item.strip()]
    if traits:
        payload["variant_traits"] = traits

    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"CREATED: {path}")
    print("Family/species identity and universal coloring rules are inherited.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
