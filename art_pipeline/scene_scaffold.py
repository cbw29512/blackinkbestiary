from __future__ import annotations

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


def _arch(draw, box, width: int, height: int, line_width: int, depth: bool = False) -> None:
    x0, y0, x1, y1 = _bbox(box, width, height)
    radius = max(8, (x1 - x0) // 2)
    spring = y0 + radius
    draw.line((x0, spring, x0, y1), fill="black", width=line_width)
    draw.line((x1, spring, x1, y1), fill="black", width=line_width)
    draw.arc((x0, y0, x1, y0 + 2 * radius), 180, 360, fill="black", width=line_width)
    draw.line((x0, y1, x1, y1), fill="black", width=line_width)
    if depth:
        inset = max(line_width * 3, int((x1 - x0) * 0.08))
        ix0, iy0, ix1, iy1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
        iradius = max(8, (ix1 - ix0) // 2)
        ispring = iy0 + iradius
        draw.line((ix0, ispring, ix0, iy1), fill="black", width=max(2, line_width - 1))
        draw.line((ix1, ispring, ix1, iy1), fill="black", width=max(2, line_width - 1))
        draw.arc((ix0, iy0, ix1, iy0 + 2 * iradius), 180, 360, fill="black", width=max(2, line_width - 1))
        # Perspective continuation lines inside the opening keep it from becoming a blank void.
        cx = (ix0 + ix1) // 2
        vanish_y = int(iy0 + (iy1 - iy0) * 0.58)
        draw.line((ix0, iy1, cx, vanish_y), fill="black", width=max(2, line_width - 1))
        draw.line((ix1, iy1, cx, vanish_y), fill="black", width=max(2, line_width - 1))
        for frac in (0.72, 0.82, 0.91):
            y = int(vanish_y + (iy1 - vanish_y) * frac)
            half = int((ix1 - ix0) * (frac - 0.58) * 0.42)
            draw.line((cx - half, y, cx + half, y), fill="black", width=max(2, line_width - 1))


def _door(draw, box, width: int, height: int, line_width: int, arched: bool = False) -> None:
    x0, y0, x1, y1 = _bbox(box, width, height)
    if arched:
        _arch(draw, box, width, height, line_width, depth=False)
    else:
        draw.rectangle((x0, y0, x1, y1), outline="black", width=line_width)
    inset = max(line_width * 3, int((x1 - x0) * 0.08))
    draw.rectangle((x0 + inset, y0 + inset, x1 - inset, y1 - inset), outline="black", width=max(2, line_width - 1))
    knob_x = int(x1 - inset * 1.7)
    knob_y = int((y0 + y1) / 2)
    r = max(3, line_width)
    draw.ellipse((knob_x - r, knob_y - r, knob_x + r, knob_y + r), outline="black", width=max(2, line_width - 1))


def _pit(draw, points: Iterable, width: int, height: int, line_width: int, spikes: bool = True) -> None:
    poly = [_xy(p, width, height) for p in points]
    draw.polygon(poly, outline="black")
    draw.line(poly + [poly[0]], fill="black", width=line_width, joint="curve")
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
    for i in range(count):
        x = int(left + (i + 0.5) * span / count)
        half = max(5, span // (count * 5))
        draw.line((x - half, base_y, x, tip_y, x + half, base_y), fill="black", width=max(2, line_width - 1))


def _connector(draw, primitive: dict, width: int, height: int, line_width: int) -> None:
    start = _xy(primitive["from"], width, height)
    end = _xy(primitive["to"], width, height)
    connector_width = max(2, int(primitive.get("line_width") or line_width - 1))
    draw.line((start, end), fill="black", width=connector_width)
    r = max(4, connector_width * 2)
    for x, y in (start, end):
        draw.ellipse((x - r, y - r, x + r, y + r), outline="black", width=max(2, connector_width))


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

    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError("Structural scaffold generation requires Pillow.") from exc

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    line_width = int(cfg.get("line_width") or 4)

    for primitive in cfg.get("primitives") or []:
        kind = str(primitive.get("type") or "").strip().lower()
        if kind == "line":
            draw.line(
                (*_xy(primitive["from"], width, height), *_xy(primitive["to"], width, height)),
                fill="black",
                width=max(2, int(primitive.get("line_width") or line_width)),
            )
        elif kind == "polyline":
            points = [_xy(p, width, height) for p in primitive.get("points") or []]
            if len(points) >= 2:
                draw.line(points, fill="black", width=line_width, joint="curve")
        elif kind == "polygon":
            points = [_xy(p, width, height) for p in primitive.get("points") or []]
            if len(points) >= 3:
                draw.line(points + [points[0]], fill="black", width=line_width, joint="curve")
        elif kind == "rect":
            draw.rectangle(_bbox(primitive["bbox"], width, height), outline="black", width=line_width)
        elif kind == "door":
            _door(
                draw,
                primitive["bbox"],
                width,
                height,
                line_width,
                arched=bool(primitive.get("arched")),
            )
        elif kind == "archway":
            _arch(
                draw,
                primitive["bbox"],
                width,
                height,
                line_width,
                depth=bool(primitive.get("depth", True)),
            )
        elif kind == "pit":
            _pit(
                draw,
                primitive.get("points") or [],
                width,
                height,
                line_width,
                spikes=bool(primitive.get("spikes", True)),
            )
        elif kind == "connector":
            _connector(draw, primitive, width, height, line_width)
        else:
            raise ValueError(f"Unsupported scene scaffold primitive: {kind!r}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
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
        anchors = primitive.get("anchors") or ["fixed endpoint", "fixed endpoint"]
        connector_rules.append(
            f"{role}: preserve exactly two visible endpoints anchored to {anchors[0]} and {anchors[1]}; "
            "do not attach, merge, or terminate the line on the creature unless the page explicitly requires that interaction."
        )

    opening_rule = str(cfg.get("opening_rule") or "").strip()
    subject_rule = str(cfg.get("subject_rule") or "").strip()
    topology = " ".join(connector_rules)
    return (
        "STRUCTURAL SCAFFOLD MODE — HARD GEOMETRY AUTHORITY: the provided input image is a layout scaffold, not finished artwork. "
        "Preserve the topology and placement of its major black-line structures while converting them into polished fantasy coloring-page architecture. "
        "Do not erase, relocate, or reinterpret the scaffold's openings, hazards, doors, or connector endpoints. "
        "Every architectural opening must contain visible depth evidence such as receding floor/wall lines, a back plane, or continuing passage; never leave a large doorway or arch as an empty white void. "
        + (opening_rule + " " if opening_rule else "")
        + (subject_rule + " " if subject_rule else "")
        + topology
    ).strip()
