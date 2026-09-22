from __future__ import annotations

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


def inspect_line_art(path: str | Path) -> dict:
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
    min_luma, max_luma = 255, 0

    for y in range(0, height, y_step):
        row = rows[y]
        for x in range(0, width, x_step):
            i = x * channels
            if color_type in {0, 4}:
                luma = row[i]
            else:
                r, g, b = row[i], row[i + 1], row[i + 2]
                luma = (299 * r + 587 * g + 114 * b) // 1000
            dark += luma < 80
            white += luma > 245
            total += 1
            min_luma = min(min_luma, luma)
            max_luma = max(max_luma, luma)

    dark_ratio = dark / total if total else 0.0
    white_ratio = white / total if total else 0.0
    reasons = []
    if dark_ratio < 0.001:
        reasons.append("near_blank_page")
    if dark_ratio > 0.55:
        reasons.append("overly_dark_page")
    if max_luma - min_luma < 35:
        reasons.append("insufficient_contrast")

    return {
        "supported": True,
        "dark_ratio": round(dark_ratio, 4),
        "white_ratio": round(white_ratio, 4),
        "contrast_range": max_luma - min_luma,
        "pass": not reasons,
        "reasons": reasons,
    }
