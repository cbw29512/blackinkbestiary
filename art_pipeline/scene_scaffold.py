from __future__ import annotations

import binascii
import math
import struct
import zlib
from pathlib import Path
from typing import Iterable


def scaffold_config(page: dict) -> dict:
    value = page.get("scene_scaffold") or {}
    return value if isinstance(value, dict) else {}


def scaffold_enabled(page: dict) -> bool:
    cfg = scaffold_config(page)
    return bool(cfg.get("enabled") and cfg.get("primitives"))


def _xy(point, width: int, height: int) -> tuple[int, int]:
    x, y = point
    return int(round(float(x) * width)), int(round(float(y) * height))


def _bbox(box, width: int, height: int) -> tuple[int, int, int, int]:
    x0, y0 = _xy((box[0], box[1]), width, height)
    x1, y1 = _xy((box[2], box[3]), width, height)
    return x0, y0, x1, y1


def _set_black(canvas: bytearray, width: int, height: int, x: int, y: int, line_width: int = 1) -> None:
    radius = max(0, int(line_width) // 2)
    for yy in range(y - radius, y + radius + 1):
        if yy < 0 or yy >= height:
            continue
        row = yy * width
        for xx in range(x - radius, x + radius + 1):
            if 0 <= xx < width:
                canvas[row + xx] = 0


def _line(canvas: bytearray, width: int, height: int, start, end, line_width: int = 1) -> None:
    x0, y0 = map(int, start)
    x1, y1 = map(int, end)
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _set_black(canvas, width, height, x0, y0, line_width)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _polyline(canvas: bytearray, width: int, height: int, points: list[tuple[int, int]], line_width: int) -> None:
    for left, right in zip(points, points[1:]):
        _line(canvas, width, height, left, right, line_width)


def _rectangle(canvas: bytearray, width: int, height: int, box, line_width: int) -> None:
    x0, y0, x1, y1 = map(int, box)
    _polyline(
        canvas,
        width,
        height,
        [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
        line_width,
    )


def _arc_points(box, start_degrees: float, end_degrees: float, steps: int = 48) -> list[tuple[int, int]]:
    x0, y0, x1, y1 = map(float, box)
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    rx = abs(x1 - x0) / 2.0
    ry = abs(y1 - y0) / 2.0
    result = []
    for index in range(steps + 1):
        angle = math.radians(start_degrees + (end_degrees - start_degrees) * index / steps)
        result.append((int(round(cx + rx * math.cos(angle))), int(round(cy + ry * math.sin(angle)))))
    return result


def _circle(canvas: bytearray, width: int, height: int, center, radius: int, line_width: int) -> None:
    cx, cy = center
    points = []
    for index in range(32):
        angle = 2.0 * math.pi * index / 32.0
        points.append((int(round(cx + radius * math.cos(angle))), int(round(cy + radius * math.sin(angle)))))
    points.append(points[0])
    _polyline(canvas, width, height, points, line_width)


def _arch(canvas: bytearray, box, width: int, height: int, line_width: int, depth: bool = False) -> None:
    x0, y0, x1, y1 = _bbox(box, width, height)
    radius = max(8, (x1 - x0) // 2)
    spring = y0 + radius
    _line(canvas, width, height, (x0, spring), (x0, y1), line_width)
    _line(canvas, width, height, (x1, spring), (x1, y1), line_width)
    _polyline(canvas, width, height, _arc_points((x0, y0, x1, y0 + 2 * radius), 180, 360), line_width)
    _line(canvas, width, height, (x0, y1), (x1, y1), line_width)

    if depth:
        inset = max(line_width * 3, int((x1 - x0) * 0.08))
        ix0, iy0, ix1, iy1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
        iradius = max(8, (ix1 - ix0) // 2)
        ispring = iy0 + iradius
        inner_width = max(2, line_width - 1)
        _line(canvas, width, height, (ix0, ispring), (ix0, iy1), inner_width)
        _line(canvas, width, height, (ix1, ispring), (ix1, iy1), inner_width)
        _polyline(canvas, width, height, _arc_points((ix0, iy0, ix1, iy0 + 2 * iradius), 180, 360), inner_width)

        cx = (ix0 + ix1) // 2
        vanish_y = int(iy0 + (iy1 - iy0) * 0.58)
        _line(canvas, width, height, (ix0, iy1), (cx, vanish_y), inner_width)
        _line(canvas, width, height, (ix1, iy1), (cx, vanish_y), inner_width)
        for frac in (0.72, 0.82, 0.91):
            y = int(vanish_y + (iy1 - vanish_y) * frac)
            half = int((ix1 - ix0) * (frac - 0.58) * 0.42)
            _line(canvas, width, height, (cx - half, y), (cx + half, y), inner_width)


def _door(canvas: bytearray, box, width: int, height: int, line_width: int, arched: bool = False) -> None:
    x0, y0, x1, y1 = _bbox(box, width, height)
    if arched:
        _arch(canvas, box, width, height, line_width, depth=False)
    else:
        _rectangle(canvas, width, height, (x0, y0, x1, y1), line_width)
    inset = max(line_width * 3, int((x1 - x0) * 0.08))
    _rectangle(canvas, width, height, (x0 + inset, y0 + inset, x1 - inset, y1 - inset), max(2, line_width - 1))
    knob_x = int(x1 - inset * 1.7)
    knob_y = int((y0 + y1) / 2)
    _circle(canvas, width, height, (knob_x, knob_y), max(3, line_width), max(2, line_width - 1))


def _pit(canvas: bytearray, points: Iterable, width: int, height: int, line_width: int, spikes: bool = True, open_near: bool = False) -> None:
    poly = [_xy(p, width, height) for p in points]
    if len(poly) < 3:
        return
    if open_near and len(poly) >= 4:
        far_left, far_right, near_right, near_left = poly[:4]
        _polyline(canvas, width, height, [near_left, far_left, far_right, near_right], line_width)

        def _mix(a, b, t):
            return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t))

        _line(canvas, width, height, _mix(far_left, near_left, 0.42), _mix(far_right, near_right, 0.42), max(2, line_width - 1))
        if spikes:
            for index, t in enumerate((0.28, 0.5, 0.72)):
                base = _mix(near_left, near_right, t)
                tip = _mix(far_left, far_right, t)
                tip = _mix(tip, base, 0.45)
                _line(canvas, width, height, base, tip, max(2, line_width - 1))
        return
    _polyline(canvas, width, height, poly + [poly[0]], line_width)
    if not spikes or len(poly) < 4:
        return
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    span = max(20, right - left)
    count = max(4, min(9, span // 45))
    base_y = int(top + (bottom - top) * 0.72)
    tip_y = int(top + (bottom - top) * 0.30)
    for index in range(count):
        x = int(left + (index + 0.5) * span / count)
        half = max(5, span // (count * 5))
        _polyline(canvas, width, height, [(x - half, base_y), (x, tip_y), (x + half, base_y)], max(2, line_width - 1))


def _connector(canvas: bytearray, primitive: dict, width: int, height: int, line_width: int) -> None:
    start = _xy(primitive["from"], width, height)
    end = _xy(primitive["to"], width, height)
    connector_width = max(2, int(primitive.get("line_width") or line_width - 1))
    _line(canvas, width, height, start, end, connector_width)
    radius = max(4, connector_width * 2)
    _circle(canvas, width, height, start, radius, max(2, connector_width))
    _circle(canvas, width, height, end, radius, max(2, connector_width))


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(chunk_type + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)


def _write_grayscale_png(path: Path, canvas: bytearray, width: int, height: int) -> None:
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        start = y * width
        rows.extend(canvas[start:start + width])
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(payload)


def render_scene_scaffold(
    page: dict,
    output_path: Path,
    *,
    width: int = 768,
    height: int = 1024,
) -> Path | None:
    cfg = scaffold_config(page)
    if not scaffold_enabled(page):
        return None
    if width < 32 or height < 32:
        raise ValueError("Structural scaffold dimensions are too small.")

    canvas = bytearray([255]) * (width * height)
    line_width = int(cfg.get("line_width") or 4)

    for primitive in cfg.get("primitives") or []:
        kind = str(primitive.get("type") or "").strip().lower()
        if kind == "line":
            _line(canvas, width, height, _xy(primitive["from"], width, height), _xy(primitive["to"], width, height), max(2, int(primitive.get("line_width") or line_width)))
        elif kind == "polyline":
            points = [_xy(p, width, height) for p in primitive.get("points") or []]
            if len(points) >= 2:
                _polyline(canvas, width, height, points, line_width)
        elif kind == "polygon":
            points = [_xy(p, width, height) for p in primitive.get("points") or []]
            if len(points) >= 3:
                _polyline(canvas, width, height, points + [points[0]], line_width)
        elif kind == "rect":
            _rectangle(canvas, width, height, _bbox(primitive["bbox"], width, height), line_width)
        elif kind == "door":
            _door(canvas, primitive["bbox"], width, height, line_width, arched=bool(primitive.get("arched")))
        elif kind == "archway":
            _arch(canvas, primitive["bbox"], width, height, line_width, depth=bool(primitive.get("depth", True)))
        elif kind == "pit":
            _pit(canvas, primitive.get("points") or [], width, height, line_width, spikes=bool(primitive.get("spikes", True)), open_near=bool(primitive.get("open_near", False)))
        elif kind == "connector":
            _connector(canvas, primitive, width, height, line_width)
        else:
            raise ValueError(f"Unsupported scene scaffold primitive: {kind!r}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_grayscale_png(output_path, canvas, width, height)
    return output_path


def scaffold_prompt_prefix(page: dict) -> str:
    cfg = scaffold_config(page)
    if not scaffold_enabled(page):
        return ""

    connector_rules = []
    for primitive in cfg.get("primitives") or []:
        if str(primitive.get("type") or "").lower() != "connector":
            continue
        role = str(primitive.get("role") or "connector").strip()
        anchors = primitive.get("anchors") or ["wall", "wall"]
        connector_rules.append(f"{role}: two anchors ({anchors[0]}; {anchors[1]}); never on the creature.")

    opening_rule = str(cfg.get("opening_rule") or "").strip()
    subject_rule = str(cfg.get("subject_rule") or "").strip()
    pit_rule = ""
    if any(str(item.get("type") or "").lower() == "pit" and item.get("open_near") for item in cfg.get("primitives") or []):
        pit_rule = "The pit is a hole cut into the floor with the near side open toward the viewer, not a closed tray or box. "
    return (
        "SCAFFOLD MODE: input lines are layout, not finished art. Keep openings, hazards, doors, and connector endpoints. "
        "Openings need visible depth; no empty white voids. "
        + (opening_rule + " " if opening_rule else "")
        + (subject_rule + " " if subject_rule else "")
        + pit_rule
        + " ".join(connector_rules)
    ).strip()
