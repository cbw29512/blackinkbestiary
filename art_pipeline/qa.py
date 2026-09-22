from __future__ import annotations

import struct
from pathlib import Path

from png_content_qa import inspect_line_art


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def inspect_png(path: Path, target_ratio: float = 8.5 / 11, ratio_tolerance: float = 0.04) -> dict:
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

    content = inspect_line_art(path)
    result["content_qa"] = content
    if not content.get("supported"):
        result["reasons"].append("content_qa_unsupported")
    else:
        result["reasons"].extend(content.get("reasons", []))

    result["pass"] = not result["reasons"]
    return result


def inspect_candidate(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {"path": str(path), "exists": False, "pass": False, "reasons": ["missing_file"]}
    if path.suffix.lower() == ".png":
        return inspect_png(path)
    return {"path": str(path), "exists": True, "pass": False, "reasons": ["unsupported_format"]}


def inspect_kdp_export(path: str | Path) -> dict:
    result = inspect_candidate(path)
    if not result.get("exists") or result.get("format") != "png":
        return result
    exact = result.get("width") == 2550 and result.get("height") == 3300
    result["kdp_exact_dimensions"] = exact
    if not exact and "kdp_export_dimensions" not in result["reasons"]:
        result["reasons"].append("kdp_export_dimensions")
    result["pass"] = not result["reasons"]
    return result
