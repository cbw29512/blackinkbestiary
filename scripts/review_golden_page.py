from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from calibration_gate import calibration_report, load_calibration_config, validate_calibration
from calibration_state import approve_calibration_candidate, reject_calibration_candidate

LOGGER = logging.getLogger("golden-five-review")


def main() -> int:
    parser = argparse.ArgumentParser(description="Review an isolated Golden Five calibration candidate")
    parser.add_argument("page_id")
    parser.add_argument("decision", choices=("approve", "reject"))
    parser.add_argument("--failed", nargs="*", default=[])
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        errors = validate_calibration(ROOT)
        if errors:
            raise RuntimeError("Golden Five configuration invalid: " + " | ".join(errors))
        config = load_calibration_config()
        valid_ids = {item["page_id"] for item in config.get("cases", [])}
        if args.page_id not in valid_ids:
            raise RuntimeError(f"{args.page_id} is not a Golden Five page")

        if args.decision == "approve":
            if args.failed:
                raise RuntimeError("Approved calibration pages cannot include failed dimensions")
            result = approve_calibration_candidate(ROOT, args.page_id, args.notes)
        else:
            result = reject_calibration_candidate(
                ROOT,
                args.page_id,
                args.failed,
                args.notes,
            )

        print(json.dumps({
            "page": result,
            "calibration": calibration_report(ROOT),
        }, indent=2))
        return 0
    except Exception as exc:
        LOGGER.exception("Golden Five review failed")
        print(f"REVIEW FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
