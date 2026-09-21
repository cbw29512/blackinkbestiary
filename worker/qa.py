from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageStat


def inspect(path: Path, target_ratio: float = 0.75) -> dict:
    with Image.open(path) as source:
        image = source.convert("RGB")
        width, height = image.size
        thumb = image.copy()
        thumb.thumbnail((512, 512))
        pixels = list(thumb.getdata())

    total = max(1, len(pixels))
    lum = [(r * 299 + g * 587 + b * 114) / 1000 for r, g, b in pixels]
    white_ratio = sum(v >= 245 for v in lum) / total
    dark_ratio = sum(v <= 60 for v in lum) / total
    ink_ratio = sum(v < 240 for v in lum) / total
    midtone_ratio = sum(90 <= v <= 225 for v in lum) / total
    color_ratio = sum((max(p) - min(p)) > 12 for p in pixels) / total
    ratio = width / height if height else 0

    reasons = []
    if height <= width:
        reasons.append("not portrait")
    if abs(ratio - target_ratio) > 0.13:
        reasons.append(f"aspect ratio {ratio:.3f} outside portrait target")
    if white_ratio < 0.50:
        reasons.append(f"too little open white area ({white_ratio:.0%})")
    if dark_ratio > 0.22:
        reasons.append(f"too much heavy black coverage ({dark_ratio:.0%})")
    if ink_ratio < 0.025:
        reasons.append("page is nearly blank")
    if ink_ratio > 0.48:
        reasons.append(f"line/detail coverage too dense ({ink_ratio:.0%})")
    if midtone_ratio > 0.24:
        reasons.append(f"too much gray/midtone rendering ({midtone_ratio:.0%})")
    if color_ratio > 0.015:
        reasons.append(f"color contamination detected ({color_ratio:.1%})")

    score = 100.0
    score -= min(30.0, abs(white_ratio - 0.70) * 100)
    score -= min(20.0, max(0.0, dark_ratio - 0.10) * 120)
    score -= min(20.0, max(0.0, midtone_ratio - 0.08) * 100)
    score -= min(20.0, color_ratio * 500)
    score -= min(10.0, abs(ratio - target_ratio) * 40)

    return {
        "passed": not reasons,
        "score": round(max(0.0, score), 1),
        "width": width,
        "height": height,
        "aspect_ratio": round(ratio, 4),
        "white_ratio": round(white_ratio, 4),
        "dark_ratio": round(dark_ratio, 4),
        "ink_ratio": round(ink_ratio, 4),
        "midtone_ratio": round(midtone_ratio, 4),
        "color_ratio": round(color_ratio, 4),
        "reasons": reasons,
    }


def choose_best(results: list[dict]) -> dict | None:
    passed = [item for item in results if item["qa"]["passed"]]
    if not passed:
        return None
    return max(passed, key=lambda item: item["qa"]["score"])
