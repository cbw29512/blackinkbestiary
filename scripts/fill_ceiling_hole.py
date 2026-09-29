"""Draw colorable joists into the blank ceiling hole of an existing page.

Does not call Flux. Edits the local PNG only.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def fill_hole(src: Path, dest: Path) -> None:
    image = Image.open(src).convert("RGB")
    width, height = image.size

    top = 0
    bottom = int(height * 0.22)
    left = int(width * 0.18)
    right = int(width * 0.82)

    def is_blank(x: int, y: int) -> bool:
        r, g, b = image.getpixel((x, y))
        return r > 240 and g > 240 and b > 240

    joist_xs = [
        int(width * 0.28),
        int(width * 0.40),
        int(width * 0.52),
        int(width * 0.64),
    ]
    for x in joist_xs:
        for y in range(top + 8, bottom):
            if 2 <= x < width - 2 and is_blank(x, y):
                image.putpixel((max(0, x - 4), y), (0, 0, 0))
                image.putpixel((min(width - 1, x + 4), y), (0, 0, 0))

    for y in range(top + 12, bottom - 4, 18):
        for x in range(left, right):
            if is_blank(x, y):
                image.putpixel((x, y), (0, 0, 0))

    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest)
    print(f"Saved {dest}")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/fill_ceiling_hole.py web/kdp-pages/I-08.png")
        return 2
    src = Path(sys.argv[1])
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_name(src.stem + "-filled.png")
    fill_hole(src, dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
