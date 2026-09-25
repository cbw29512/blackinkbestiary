from __future__ import annotations

import hashlib
import json
import zlib
from pathlib import Path

try:
    from .png_content_qa import _decode_rows
    from .qa import inspect_kdp_export
except ImportError:
    from png_content_qa import _decode_rows
    from qa import inspect_kdp_export

PAGE_WIDTH_PT = 612
PAGE_HEIGHT_PT = 792


def _pdf_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def attribution_lines(root: Path) -> list[str]:
    path = root / "config" / "source_attribution.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    required = (
        "heading",
        "work_title",
        "attribution_party",
        "source_url",
        "license_name",
        "license_short_name",
        "license_url",
    )
    missing = [key for key in required if not str(config.get(key) or "").strip()]
    if missing:
        raise RuntimeError(
            "source attribution config is incomplete: " + ", ".join(missing)
        )
    if str(config.get("placement") or "") != "append_final_page":
        raise RuntimeError("source attribution placement must be append_final_page")
    if bool(config.get("additional_wizards_attribution")):
        raise RuntimeError("additional Wizards attribution is not permitted by project policy")

    return [
        str(config["heading"]),
        "",
        str(config["work_title"]),
        f"By {config['attribution_party']}",
        f"Source: {config['source_url']}",
        "",
        f"Licensed under {config['license_name']} ({config['license_short_name']})",
        f"License: {config['license_url']}",
    ]


def _text_page_content(lines: list[str]) -> bytes:
    commands = [
        "BT",
        "/F1 18 Tf",
        "72 720 Td",
    ]
    first = True
    for line in lines:
        if not first:
            commands.append("0 -24 Td")
        first = False
        if line:
            commands.append(f"({_pdf_escape(line)}) Tj")
    commands.append("ET")
    return ("\n".join(commands) + "\n").encode("ascii")


def _png_pixels(path: Path) -> tuple[int, int, str, bytes]:
    raw = path.read_bytes()
    width, height, color_type, rows = _decode_rows(raw)

    if color_type == 0:
        return width, height, "/DeviceGray", b"".join(rows)

    if color_type == 2:
        return width, height, "/DeviceRGB", b"".join(rows)

    if color_type == 4:
        out = bytearray()
        for row in rows:
            for i in range(0, len(row), 2):
                gray, alpha = row[i], row[i + 1]
                out.append((gray * alpha + 255 * (255 - alpha)) // 255)
        return width, height, "/DeviceGray", bytes(out)

    if color_type == 6:
        out = bytearray()
        for row in rows:
            for i in range(0, len(row), 4):
                r, g, b, alpha = row[i:i + 4]
                out.extend((
                    (r * alpha + 255 * (255 - alpha)) // 255,
                    (g * alpha + 255 * (255 - alpha)) // 255,
                    (b * alpha + 255 * (255 - alpha)) // 255,
                ))
        return width, height, "/DeviceRGB", bytes(out)

    raise ValueError(f"unsupported_png_color_type:{color_type}")


def assemble_pdf(
    image_paths: list[Path],
    output_path: Path,
    *,
    title: str = "Black Ink Bestiary",
    credits_lines: list[str] | None = None,
) -> dict:
    """Build a deterministic 8.5x11 PDF from ordered PNG pages plus optional credits."""
    if not image_paths:
        raise ValueError("no_pages_to_assemble")

    page_payloads = []
    for path in image_paths:
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(path)
        width, height, color_space, pixels = _png_pixels(path)
        page_payloads.append({
            "path": path,
            "width": width,
            "height": height,
            "color_space": color_space,
            "pixels": zlib.compress(pixels, 9),
        })

    objects: list[bytes] = []
    objects.append(b"")  # 1 catalog placeholder
    objects.append(b"")  # 2 pages placeholder

    page_refs = []
    for index, payload in enumerate(page_payloads, start=1):
        image_obj = len(objects) + 1
        image_stream = payload["pixels"]
        objects.append(
            (
                f"<< /Type /XObject /Subtype /Image /Width {payload['width']} "
                f"/Height {payload['height']} /ColorSpace {payload['color_space']} "
                f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(image_stream)} >>\n"
                "stream\n"
            ).encode("ascii")
            + image_stream
            + b"\nendstream"
        )

        content_obj = len(objects) + 1
        content = (
            f"q {PAGE_WIDTH_PT} 0 0 {PAGE_HEIGHT_PT} 0 0 cm /Im{index} Do Q\n"
        ).encode("ascii")
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode("ascii")
            + content
            + b"endstream"
        )

        page_obj = len(objects) + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {PAGE_WIDTH_PT} {PAGE_HEIGHT_PT}] "
                f"/Resources << /XObject << /Im{index} {image_obj} 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            ).encode("ascii")
        )
        page_refs.append(page_obj)

    if credits_lines:
        font_obj = len(objects) + 1
        objects.append(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
        )
        credits_content = _text_page_content(credits_lines)
        content_obj = len(objects) + 1
        objects.append(
            f"<< /Length {len(credits_content)} >>\nstream\n".encode("ascii")
            + credits_content
            + b"endstream"
        )
        page_obj = len(objects) + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {PAGE_WIDTH_PT} {PAGE_HEIGHT_PT}] "
                f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            ).encode("ascii")
        )
        page_refs.append(page_obj)

    objects[1] = (
        f"<< /Type /Pages /Count {len(page_refs)} /Kids ["
        + " ".join(f"{ref} 0 R" for ref in page_refs)
        + "] >>"
    ).encode("ascii")
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"

    info_obj = len(objects) + 1
    objects.append(
        (
            f"<< /Title ({_pdf_escape(title)}) "
            f"/Producer (Black Ink Bestiary deterministic assembler) >>"
        ).encode("ascii")
    )

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R "
            f"/Info {info_obj} 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(output))
    digest = hashlib.sha256(output).hexdigest()
    return {
        "output": str(output_path),
        "pages": len(page_refs),
        "art_pages": len(image_paths),
        "credits_page": bool(credits_lines),
        "sha256": digest,
        "bytes": len(output),
        "page_width_pt": PAGE_WIDTH_PT,
        "page_height_pt": PAGE_HEIGHT_PT,
    }


def binding_side_for_page(page_number: int) -> str:
    if page_number < 1:
        raise ValueError("page_number must be at least 1")
    # Odd interior pages are recto/right-hand pages; their binding edge is left.
    return "left" if page_number % 2 == 1 else "right"


def locked_page_paths(root: Path, manifest: dict, state: dict) -> list[Path]:
    ordered = []
    pages = sorted(
        manifest.get("pages") or [],
        key=lambda item: int(item.get("order") or 0),
    )
    for page_number, page in enumerate(pages, start=1):
        page_id = str(page.get("page_id") or "")
        entry = (state.get("pages") or {}).get(page_id) or {}
        if entry.get("status") != "locked":
            raise RuntimeError(f"{page_id}: page is not locked")
        relative = str(entry.get("approved_image_path") or "").strip()
        if not relative:
            raise RuntimeError(f"{page_id}: locked page has no approved_image_path")
        path = root / "web" / relative
        binding_side = binding_side_for_page(page_number)
        report = inspect_kdp_export(path, binding_side=binding_side)
        if not report.get("pass"):
            raise RuntimeError(
                f"{page_id}: approved page is not KDP-export ready "
                f"(binding={binding_side}): "
                + ", ".join(report.get("reasons") or ["unknown"])
            )
        ordered.append(path)
    if len(ordered) != int(manifest.get("total_pages") or 0):
        raise RuntimeError("locked page count does not match manifest total_pages")
    return ordered


def assemble_locked_book(
    root: Path,
    manifest: dict,
    state: dict,
    output_path: Path,
) -> dict:
    pages = locked_page_paths(root, manifest, state)
    title = str(manifest.get("title") or manifest.get("tome_id") or "Black Ink Bestiary")
    credits = attribution_lines(root)
    report = assemble_pdf(
        pages,
        output_path,
        title=title,
        credits_lines=credits,
    )
    report["book_id"] = manifest.get("tome_id") or manifest.get("book_id")
    report["title"] = title
    report["attribution_source_id"] = "dnd-srd-5.2.1"
    return report
