from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from book_assembly import assemble_locked_book
from studio_config import active_book_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble the active locked coloring book into a deterministic KDP interior PDF")
    parser.add_argument("--output", default="build/final-interior.pdf")
    parser.add_argument("--report", default="build/final-interior.json")
    args = parser.parse_args()

    paths = active_book_paths(ROOT)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    state = json.loads(paths["state"].read_text(encoding="utf-8"))
    output = ROOT / args.output
    report_path = ROOT / args.report

    report = assemble_locked_book(ROOT, manifest, state, output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
