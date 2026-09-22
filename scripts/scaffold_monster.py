from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONSTER_DIR = ROOT / "data" / "monsters"
FAMILY_DIR = ROOT / "data" / "monster_families"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a minimal engine-driven monster recipe.")
    parser.add_argument("monster_id")
    parser.add_argument("monster_name")
    parser.add_argument("family_profile")
    parser.add_argument("--traits", default="", help="Comma-separated variant traits")
    args = parser.parse_args()

    family_path = FAMILY_DIR / f"{args.family_profile}.json"
    if not family_path.exists():
        print(f"REFUSED: unknown family profile {args.family_profile!r}")
        return 2

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
    if traits:
        payload["variant_traits"] = traits

    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"CREATED: {path}")
    print("Family DNA and universal coloring rules will be inherited automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
