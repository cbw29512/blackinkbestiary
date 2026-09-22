from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "art_pipeline"))
from source_scope import monster_allowed

ROOT = Path(__file__).resolve().parents[1]
MONSTER_DIR = ROOT / "data" / "monsters"
FAMILY_DIR = ROOT / "data" / "monster_families"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a minimal engine-driven monster recipe.")
    parser.add_argument("monster_id")
    parser.add_argument("monster_name")
    parser.add_argument("family_profile")
    parser.add_argument("--variant", default="", help="Optional reusable variant profile ID")
    parser.add_argument("--traits", default="", help="Comma-separated variant traits")
    args = parser.parse_args()

    if not monster_allowed(args.monster_id, ROOT):
        print(f"REFUSED: {args.monster_id!r} is not on the approved 2024 SRD project roster.")
        return 4

    family_path = FAMILY_DIR / f"{args.family_profile}.json"
    if not family_path.exists():
        print(f"REFUSED: unknown family profile {args.family_profile!r}")
        return 2

    variant_id = args.variant.strip()
    if variant_id:
        variant_path = ROOT / "data" / "monster_variants" / f"{variant_id}.json"
        if not variant_path.exists():
            print(f"REFUSED: unknown variant profile {variant_id!r}")
            return 5
        variant = json.loads(variant_path.read_text(encoding="utf-8"))
        if variant.get("family_profile") != args.family_profile:
            print(
                f"REFUSED: variant {variant_id!r} belongs to "
                f"{variant.get('family_profile')!r}, not {args.family_profile!r}"
            )
            return 6

    path = MONSTER_DIR / f"{args.monster_id}.json"
    if path.exists():
        print(f"REFUSED: monster already exists: {path}")
        return 3

    traits = [item.strip() for item in args.traits.split(",") if item.strip()]
    payload = {
        "schema_version": 3,
        "monster_id": args.monster_id,
        "monster_name": args.monster_name,
        "family_profile": args.family_profile,
    }
    if variant_id:
        payload["variant_profile"] = variant_id
    if traits:
        payload["variant_traits"] = traits

    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"CREATED: {path}")
    print("Family DNA and universal coloring rules will be inherited automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
