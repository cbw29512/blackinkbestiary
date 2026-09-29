#!/usr/bin/env python3
"""Validate that director briefs request original compositions."""
from __future__ import annotations
import json
import logging
from pathlib import Path
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOG = logging.getLogger("director_originality")
DISALLOWED = ("official look", "copy official", "official art", "reference image", "classic fr")


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def main() -> int:
    try:
        problems = []
        files = sorted(Path("data/director").glob("*.json"))
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            combined = "\n".join(strings(data)).lower()
            matches = [term for term in DISALLOWED if term in combined]
            if matches:
                problems.append(f"{path}: {', '.join(matches)}")
        if problems:
            for problem in problems:
                LOG.error("%s", problem)
            return 1
        LOG.info("Originality check passed for %d director files.", len(files))
        return 0
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        LOG.exception("Originality check failed to run: %s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
