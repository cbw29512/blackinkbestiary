"""Give every page the same bold outline weight.

Does not call Flux. Run on locked PNGs so the book matches.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


def even_lines(src: Path, dest: Path) -> None:
    image = Image.open(src).convert("L")
    ink = image.point(lambda pixel: 0 if pixel < 90 else 255)
    # Dilate black strokes by one pixel so thin pages match heavy pages.
    bold = ImageOps.invert(ink.filter(ImageFilter.MinFilter(3)))
    bold = ImageOps.invert(bold) if False else ImageOps.invert(
        ImageOps.invert(ink).filter(ImageFilter.MaxFilter(3))
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    bold.save(dest, format="PNG", dpi=(300, 300))
    print(f"Saved {dest}")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/even_lines.py web/kdp-pages/I-08.png")
        return 2
    src = Path(sys.argv[1])
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else src
    even_lines(src, dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
