from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _pixel_metrics(path: Path) -> dict:
    with Image.open(path) as source:
        rgba = source.convert("RGBA")
        rgba.thumbnail((512, 512))
        white_bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        rgb = Image.alpha_composite(white_bg, rgba).convert("RGB")

    total = max(1, rgb.width * rgb.height)
    white = dark = midtone = colored = 0

    for red, green, blue in rgb.getdata():
        high = max(red, green, blue)
        low = min(red, green, blue)
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue

        if low >= 245:
            white += 1
        if luminance <= 70:
            dark += 1
        if 70 < luminance < 235:
            midtone += 1
        if high - low > 18 and luminance < 248:
            colored += 1

    metrics = {
        "sample_width": rgb.width,
        "sample_height": rgb.height,
        "white_fraction": round(white / total, 4),
        "dark_fraction": round(dark / total, 4),
        "midtone_fraction": round(midtone / total, 4),
        "color_fraction": round(colored / total, 4),
    }

    # This score is intentionally style-only. It does not claim to judge
    # monster identity or anatomy; the human reviewer still owns those calls.
    score = 100.0
    score -= max(0.0, 0.65 - metrics["white_fraction"]) * 180
    score -= max(0.0, metrics["dark_fraction"] - 0.14) * 170
    score -= max(0.0, metrics["midtone_fraction"] - 0.10) * 160
    score -= metrics["color_fraction"] * 500
    metrics["style_score"] = round(max(0.0, min(100.0, score)), 1)
    return metrics


def inspect_png(path: Path, target_ratio: float = 3 / 4, ratio_tolerance: float = 0.08) -> dict:
    raw = path.read_bytes()
    result = {
        "path": str(path),
        "exists": True,
        "format": None,
        "width": None,
        "height": None,
        "portrait": False,
        "aspect_ratio": None,
        "aspect_ok": False,
        "minimum_size_ok": False,
        "file_size_bytes": len(raw),
        "metrics": {},
        "style_score": 0.0,
        "warnings": [],
        "pass": False,
        "reasons": [],
    }

    if not raw.startswith(PNG_SIGNATURE):
        result["reasons"].append("not_png")
        return result

    result["format"] = "png"
    if len(raw) < 24 or raw[12:16] != b"IHDR":
        result["reasons"].append("invalid_png_header")
        return result

    width, height = struct.unpack(">II", raw[16:24])
    result["width"] = width
    result["height"] = height
    result["portrait"] = height > width
    ratio = width / height if height else 0
    result["aspect_ratio"] = round(ratio, 4)
    result["aspect_ok"] = abs(ratio - target_ratio) <= ratio_tolerance
    result["minimum_size_ok"] = width >= 768 and height >= 1024

    if not result["portrait"]:
        result["reasons"].append("not_portrait")
    if not result["aspect_ok"]:
        result["reasons"].append("unexpected_aspect_ratio")
    if not result["minimum_size_ok"]:
        result["reasons"].append("resolution_too_small")
    if len(raw) < 20_000:
        result["reasons"].append("suspiciously_small_file")

    try:
        metrics = _pixel_metrics(path)
    except Exception as exc:
        result["reasons"].append("pixel_analysis_failed")
        result["pixel_error"] = str(exc)
        result["pass"] = False
        return result

    result["metrics"] = metrics
    result["style_score"] = metrics["style_score"]

    # Hard garbage-filter thresholds. These are deliberately more permissive
    # than the Style Bible; warnings below drive refinement without throwing
    # away a potentially useful near-miss.
    if metrics["color_fraction"] > 0.03:
        result["reasons"].append("too_much_color")
    if metrics["white_fraction"] < 0.45:
        result["reasons"].append("not_enough_open_white_space")
    if metrics["dark_fraction"] > 0.35:
        result["reasons"].append("too_much_dark_coverage")
    if metrics["midtone_fraction"] > 0.35:
        result["reasons"].append("too_much_grayscale_or_shading")

    if metrics["white_fraction"] < 0.65:
        result["warnings"].append("white_space_below_house_target")
    if metrics["dark_fraction"] > 0.16:
        result["warnings"].append("dark_coverage_above_house_target")
    if metrics["midtone_fraction"] > 0.12:
        result["warnings"].append("gray_or_shading_above_house_target")
    if metrics["color_fraction"] > 0.005:
        result["warnings"].append("trace_color_detected")

    result["pass"] = not result["reasons"]
    return result


def inspect_candidate(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "pass": False,
            "style_score": 0.0,
            "reasons": ["missing_file"],
            "warnings": [],
        }
    if path.suffix.lower() == ".png":
        return inspect_png(path)
    return {
        "path": str(path),
        "exists": True,
        "pass": False,
        "style_score": 0.0,
        "reasons": ["unsupported_format"],
        "warnings": [],
    }
