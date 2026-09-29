"""Turn solid black fills into colorable white. Keep thin outlines.

Does not call Flux.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def unfill(src: Path, dest: Path, radius: int = 3) -> None:
    image = Image.open(src).convert("L")
    width, height = image.size
    src_px = image.load()
    out = Image.new("L", (width, height), 255)
    dst = out.load()

    def black(x: int, y: int) -> bool:
        return 0 <= x < width and 0 <= y < height and src_px[x, y] < 80

    for y in range(height):
        for x in range(width):
            if not black(x, y):
                continue
            edge = False
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dx == 0 and dy == 0:
                        continue
                    if not black(x + dx, y + dy):
                        edge = True
                        break
                if edge:
                    break
            if edge:
                dst[x, y] = 0

    # Drop a decorative outer frame if the rim is a solid rectangle.
    for x in range(width):
        if src_px[x, 0] < 80:
            dst[x, 0] = 255
        if src_px[x, height - 1] < 80:
            dst[x, height - 1] = 255
    for y in range(height):
        if src_px[0, y] < 80:
            dst[0, y] = 255
        if src_px[width - 1, y] < 80:
            dst[width - 1, y] = 255

    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest)
    print(f"Saved {dest}")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/unfill_black.py web/kdp-pages/I-08.png")
        return 2
    src = Path(sys.argv[1])
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else src
    unfill(src, dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
