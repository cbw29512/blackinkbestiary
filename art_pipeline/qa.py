from __future__ import annotations

import json
import struct
from pathlib import Path

from png_content_qa import _CHANNELS, _decode_rows, inspect_line_art


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


def inspect_binding_gutter(
    path: str | Path,
    binding_side: str,
    *,
    gutter_px: int,
    white_above_luma: int = 245,
    max_nonwhite_ratio: float = 0.002,
) -> dict:
    if binding_side not in {"left", "right"}:
        raise ValueError("binding_side must be left or right")
    raw = Path(path).read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        return {"supported": False, "pass": False, "reasons": ["not_png"]}

    try:
        width, height, color_type, rows = _decode_rows(raw)
    except Exception as exc:
        return {"supported": False, "pass": False, "reasons": [str(exc)]}

    channels = _CHANNELS[color_type]
    gutter_px = max(1, min(int(gutter_px), width))
    start_x = 0 if binding_side == "left" else width - gutter_px
    end_x = gutter_px if binding_side == "left" else width

    nonwhite = total = 0
    for row in rows:
        for x in range(start_x, end_x):
            i = x * channels
            if color_type in {0, 4}:
                luma = row[i]
            else:
                r, g, b = row[i], row[i + 1], row[i + 2]
                luma = (299 * r + 587 * g + 114 * b) // 1000
            nonwhite += int(luma <= white_above_luma)
            total += 1

    ratio = nonwhite / total if total else 0.0
    reasons = []
    if ratio > max_nonwhite_ratio:
        reasons.append("binding_gutter_too_busy")
    return {
        "supported": True,
        "pass": not reasons,
        "binding_side": binding_side,
        "gutter_px": gutter_px,
        "nonwhite_ratio": round(ratio, 6),
        "max_nonwhite_ratio": max_nonwhite_ratio,
        "white_above_luma": white_above_luma,
        "reasons": reasons,
    }


def inspect_candidate(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {"path": str(path), "exists": False, "pass": False, "reasons": ["missing_file"]}
    if path.suffix.lower() == ".png":
        return inspect_png(path)
    return {"path": str(path), "exists": True, "pass": False, "reasons": ["unsupported_format"]}


def inspect_kdp_export(path: str | Path, *, binding_side: str | None = None) -> dict:
    result = inspect_candidate(path)
    if not result.get("exists") or result.get("format") != "png":
        return result
    exact = result.get("width") == 2550 and result.get("height") == 3300
    result["kdp_exact_dimensions"] = exact
    if not exact and "kdp_export_dimensions" not in result["reasons"]:
        result["reasons"].append("kdp_export_dimensions")

    if binding_side and exact:
        config = json.loads(
            (ROOT / "config" / "kdp_print_standard.json").read_text(encoding="utf-8")
        )
        safe_layout = config.get("safe_layout") or {}
        validation = safe_layout.get("gutter_validation") or {}
        dpi = int((config.get("raster_export") or {}).get("dpi") or 300)
        gutter_inches = float(safe_layout.get("gutter_safe_margin_inches") or 0.5)
        gutter_px = max(1, int(round(gutter_inches * dpi)))
        gutter = inspect_binding_gutter(
            path,
            binding_side,
            gutter_px=gutter_px,
            white_above_luma=int(validation.get("white_above_luma") or 245),
            max_nonwhite_ratio=float(validation.get("max_nonwhite_ratio") or 0.002),
        )
        result["binding_gutter"] = gutter
        if not gutter.get("pass"):
            reason = str(validation.get("failure_reason") or "binding_gutter_too_busy")
            if reason not in result["reasons"]:
                result["reasons"].append(reason)

    result["pass"] = not result["reasons"]
    return result
