from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _chunks(raw: bytes):
    offset = 8
    while offset + 12 <= len(raw):
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        data = raw[offset + 8:offset + 8 + length]
        yield kind, data
        offset += 12 + length
        if kind == b"IEND":
            break


def _decode_rows(raw: bytes) -> tuple[int, int, int, list[bytes]]:
    width = height = bit_depth = color_type = interlace = None
    compressed = bytearray()
    for kind, data in _chunks(raw):
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", data
            )
        elif kind == b"IDAT":
            compressed.extend(data)

    if None in {width, height, bit_depth, color_type, interlace}:
        raise ValueError("missing_png_metadata")
    if bit_depth != 8 or interlace != 0 or color_type not in _CHANNELS:
        raise ValueError("unsupported_png_pixel_format")

    channels = _CHANNELS[color_type]
    stride = width * channels
    decoded = zlib.decompress(bytes(compressed))
    if len(decoded) != (stride + 1) * height:
        raise ValueError("unexpected_png_scanline_size")

    rows: list[bytes] = []
    previous = bytearray(stride)
    pos = 0
    for _ in range(height):
        filter_type = decoded[pos]
        source = decoded[pos + 1:pos + 1 + stride]
        pos += stride + 1
        row = bytearray(stride)
        for i, value in enumerate(source):
            left = row[i - channels] if i >= channels else 0
            up = previous[i]
            up_left = previous[i - channels] if i >= channels else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            elif filter_type == 4:
                predictor = _paeth(left, up, up_left)
            else:
                raise ValueError("unsupported_png_filter")
            row[i] = (value + predictor) & 0xFF
        rows.append(bytes(row))
        previous = row
    return width, height, color_type, rows



def _png_chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def normalize_monochrome_line_art(path: str | Path) -> dict:
    """Remove accidental RGB color deterministically before production QA."""
    path = Path(path)
    raw = path.read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        raise ValueError("not_png")

    width, height, color_type, rows = _decode_rows(raw)
    if color_type == 0:
        return {
            "path": str(path),
            "width": width,
            "height": height,
            "source_color_type": color_type,
            "changed": False,
        }

    grayscale_rows: list[bytes] = []
    for source in rows:
        out = bytearray()
        if color_type == 2:
            for i in range(0, len(source), 3):
                r, g, b = source[i:i + 3]
                out.append((299 * r + 587 * g + 114 * b) // 1000)
        elif color_type == 4:
            for i in range(0, len(source), 2):
                gray, alpha = source[i:i + 2]
                out.append((gray * alpha + 255 * (255 - alpha)) // 255)
        elif color_type == 6:
            for i in range(0, len(source), 4):
                r, g, b, alpha = source[i:i + 4]
                luma = (299 * r + 587 * g + 114 * b) // 1000
                out.append((luma * alpha + 255 * (255 - alpha)) // 255)
        else:
            raise ValueError("unsupported_png_pixel_format")
        grayscale_rows.append(bytes(out))

    scanlines = bytearray()
    for row in grayscale_rows:
        scanlines.append(0)
        scanlines.extend(row)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    path.write_bytes(
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), 6))
        + _png_chunk(b"IEND", b"")
    )
    return {
        "path": str(path),
        "width": width,
        "height": height,
        "source_color_type": color_type,
        "changed": True,
    }


def enforce_print_safe_margin(
    path: str | Path,
    margin_ratio: float = 0.045,
) -> dict:
    """Whiten the outer print-safe band deterministically before QA."""
    path = Path(path)
    raw = path.read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        raise ValueError("not_png")

    width, height, color_type, rows = _decode_rows(raw)
    channels = _CHANNELS[color_type]
    margin_x = max(1, int(round(width * margin_ratio)))
    margin_y = max(1, int(round(height * margin_ratio)))
    updated_rows: list[bytes] = []

    for y, source in enumerate(rows):
        row = bytearray(source)
        for x in range(width):
            if (
                x < margin_x
                or x >= width - margin_x
                or y < margin_y
                or y >= height - margin_y
            ):
                i = x * channels
                if color_type == 0:
                    row[i] = 255
                elif color_type == 2:
                    row[i:i + 3] = b"\xff\xff\xff"
                elif color_type == 4:
                    row[i:i + 2] = b"\xff\xff"
                elif color_type == 6:
                    row[i:i + 4] = b"\xff\xff\xff\xff"
        updated_rows.append(bytes(row))

    scanlines = bytearray()
    for row in updated_rows:
        scanlines.append(0)
        scanlines.extend(row)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    path.write_bytes(
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), 6))
        + _png_chunk(b"IEND", b"")
    )
    return {
        "path": str(path),
        "width": width,
        "height": height,
        "margin_ratio": margin_ratio,
        "margin_x": margin_x,
        "margin_y": margin_y,
    }


def inspect_line_art(path: str | Path) -> dict:
    policy = _line_art_policy()
    dark_below = int(policy["dark_below"])
    white_above = int(policy["white_above"])
    max_midtone_ratio = float(policy["max_midtone_ratio"])
    midtone_failure_reason = str(policy["failure_reason"])
    raw = Path(path).read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        return {"supported": False, "reasons": ["not_png"]}

    try:
        width, height, color_type, rows = _decode_rows(raw)
    except (ValueError, zlib.error) as exc:
        return {"supported": False, "reasons": [str(exc)]}

    channels = _CHANNELS[color_type]
    x_step = max(1, width // 256)
    y_step = max(1, height // 256)
    dark = white = total = 0
    chromatic = 0
    safe_margin_dark = safe_margin_total = 0
    min_luma, max_luma = 255, 0
    margin_x = max(1, int(width * 0.04))
    margin_y = max(1, int(height * 0.04))

    for y in range(0, height, y_step):
        row = rows[y]
        for x in range(0, width, x_step):
            i = x * channels
            if color_type in {0, 4}:
                luma = row[i]
            else:
                r, g, b = row[i], row[i + 1], row[i + 2]
                luma = (299 * r + 587 * g + 114 * b) // 1000
                if max(r, g, b) - min(r, g, b) > 12:
                    chromatic += 1
            is_dark = luma < dark_below
            dark += is_dark
            white += luma > white_above
            total += 1
            if (
                x < margin_x
                or x >= width - margin_x
                or y < margin_y
                or y >= height - margin_y
            ):
                safe_margin_total += 1
                safe_margin_dark += is_dark
            min_luma = min(min_luma, luma)
            max_luma = max(max_luma, luma)

    dark_ratio = dark / total if total else 0.0
    white_ratio = white / total if total else 0.0
    chromatic_ratio = chromatic / total if total else 0.0
    midtone = max(0, total - dark - white)
    midtone_ratio = midtone / total if total else 0.0
    safe_margin_dark_ratio = (
        safe_margin_dark / safe_margin_total if safe_margin_total else 0.0
    )
    reasons = []
    if dark_ratio < 0.001:
        reasons.append("near_blank_page")
    if dark_ratio > 0.55:
        reasons.append("overly_dark_page")
    if max_luma - min_luma < 35:
        reasons.append("insufficient_contrast")
    if chromatic_ratio > 0.01:
        reasons.append("unexpected_color_content")
    if midtone_ratio > max_midtone_ratio:
        reasons.append(midtone_failure_reason)
    if safe_margin_dark_ratio > 0.02:
        reasons.append("safe_margin_too_busy")

    return {
        "supported": True,
        "dark_ratio": round(dark_ratio, 4),
        "white_ratio": round(white_ratio, 4),
        "chromatic_ratio": round(chromatic_ratio, 4),
        "midtone_ratio": round(midtone_ratio, 4),
        "max_midtone_ratio": max_midtone_ratio,
        "safe_margin_dark_ratio": round(safe_margin_dark_ratio, 4),
        "contrast_range": max_luma - min_luma,
        "pass": not reasons,
        "reasons": reasons,
    }
