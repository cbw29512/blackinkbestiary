import struct
import tempfile
import unittest
import zlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from qa import inspect_binding_gutter, inspect_candidate
from png_content_qa import enforce_print_safe_margin, normalize_monochrome_line_art


def _chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def _write_grayscale_png(path: Path, value_fn) -> None:
    width, height = 768, 1024
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        rows.extend(value_fn(x, y) for x in range(width))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + _chunk(b"IEND", b"")
    )


def _write_rgb_png(path: Path, pixel_fn) -> None:
    width, height = 768, 1024
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.extend(pixel_fn(x, y))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + _chunk(b"IEND", b"")
    )


class PngContentQATests(unittest.TestCase):
    def test_blank_page_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blank.png"
            _write_grayscale_png(path, lambda _x, _y: 255)
            result = inspect_candidate(path)
            self.assertFalse(result["pass"])
            self.assertIn("near_blank_page", result["reasons"])

    def test_solid_dark_page_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dark.png"
            _write_grayscale_png(path, lambda _x, _y: 0)
            result = inspect_candidate(path)
            self.assertFalse(result["pass"])
            self.assertIn("overly_dark_page", result["reasons"])

    def test_simple_line_art_passes_content_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "line-art.png"
            _write_grayscale_png(
                path,
                lambda x, y: 0
                if (
                    40 <= x < 728
                    and 50 <= y < 974
                    and (x % 64 in {0, 1, 2} or y % 96 in {0, 1})
                )
                else 255,
            )
            result = inspect_candidate(path)
            self.assertTrue(result["content_qa"]["pass"])
            self.assertNotIn("near_blank_page", result["reasons"])
            self.assertNotIn("safe_margin_too_busy", result["reasons"])

    def test_heavy_midtone_shading_fails_line_art_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "midtone-heavy.png"
            _write_grayscale_png(
                path,
                lambda x, y: (
                    0
                    if (
                        40 <= x < 728
                        and 50 <= y < 974
                        and (x % 96 in {0, 1} or y % 128 in {0, 1})
                    )
                    else 160
                    if 80 <= x < 688 and 100 <= y < 924
                    else 255
                ),
            )
            result = inspect_candidate(path)
            self.assertFalse(result["pass"])
            self.assertIn("excessive_midtone_shading", result["reasons"])
            self.assertGreater(
                result["content_qa"]["midtone_ratio"],
                result["content_qa"]["max_midtone_ratio"],
            )
            self.assertEqual(result["content_qa"]["max_midtone_ratio"], 0.20)

    def test_small_midtone_area_remains_acceptable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "midtone-small.png"
            _write_grayscale_png(
                path,
                lambda x, y: (
                    0
                    if (
                        40 <= x < 728
                        and 50 <= y < 974
                        and (x % 64 in {0, 1} or y % 96 in {0, 1})
                    )
                    else 180
                    if 280 <= x < 488 and 410 <= y < 614
                    else 255
                ),
            )
            result = inspect_candidate(path)
            self.assertLess(
                result["content_qa"]["midtone_ratio"],
                result["content_qa"]["max_midtone_ratio"],
            )
            self.assertNotIn("excessive_midtone_shading", result["reasons"])

    def test_colored_output_fails_monochrome_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "colored.png"
            _write_rgb_png(
                path,
                lambda x, y: (200, 20, 20)
                if 120 <= x < 648 and 180 <= y < 844
                else (255, 255, 255),
            )
            result = inspect_candidate(path)
            self.assertFalse(result["pass"])
            self.assertIn("unexpected_color_content", result["reasons"])
            self.assertGreater(result["content_qa"]["chromatic_ratio"], 0.01)

    def test_monochrome_normalization_removes_accidental_color_before_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "colored-fixed.png"
            _write_rgb_png(
                path,
                lambda x, y: (200, 20, 20)
                if 120 <= x < 648 and 180 <= y < 844
                else (255, 255, 255),
            )
            before = inspect_candidate(path)
            self.assertIn("unexpected_color_content", before["reasons"])

            report = normalize_monochrome_line_art(path)
            after = inspect_candidate(path)

            self.assertTrue(report["changed"])
            self.assertEqual(report["source_color_type"], 2)
            self.assertEqual(after["content_qa"]["chromatic_ratio"], 0.0)
            self.assertNotIn("unexpected_color_content", after["reasons"])
            self.assertTrue(after["content_qa"]["pass"])

    def test_monochrome_normalization_is_idempotent_for_grayscale(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gray.png"
            _write_grayscale_png(
                path,
                lambda x, y: 0 if 200 <= x < 568 and 300 <= y < 724 else 255,
            )
            before = path.read_bytes()
            report = normalize_monochrome_line_art(path)
            self.assertFalse(report["changed"])
            self.assertEqual(path.read_bytes(), before)

    def test_decorative_edge_frame_fails_safe_margin_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frame.png"
            _write_grayscale_png(
                path,
                lambda x, y: 0
                if (
                    x < 5
                    or x >= 763
                    or y < 5
                    or y >= 1019
                    or (
                        300 <= x < 468
                        and 400 <= y < 624
                        and (x % 32 == 0 or y % 32 == 0)
                    )
                )
                else 255,
            )
            result = inspect_candidate(path)
            self.assertFalse(result["pass"])
            self.assertIn("safe_margin_too_busy", result["reasons"])
            self.assertGreater(result["content_qa"]["safe_margin_dark_ratio"], 0.02)


    def test_binding_gutter_rejects_ink_on_binding_side_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "binding-edge.png"
            _write_grayscale_png(
                path,
                lambda x, _y: 0 if x < 8 else 255,
            )
            left = inspect_binding_gutter(
                path,
                "left",
                gutter_px=16,
                max_nonwhite_ratio=0.10,
            )
            right = inspect_binding_gutter(
                path,
                "right",
                gutter_px=16,
                max_nonwhite_ratio=0.10,
            )
            self.assertFalse(left["pass"])
            self.assertIn("binding_gutter_too_busy", left["reasons"])
            self.assertTrue(right["pass"])

    def test_margin_enforcement_clears_edge_frame_before_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frame-fixed.png"
            _write_grayscale_png(
                path,
                lambda x, y: 0
                if (
                    x < 8
                    or x >= 760
                    or y < 8
                    or y >= 1016
                    or (
                        300 <= x < 468
                        and 400 <= y < 624
                        and (x % 32 == 0 or y % 32 == 0)
                    )
                )
                else 255,
            )
            before = inspect_candidate(path)
            self.assertIn("safe_margin_too_busy", before["reasons"])

            margin = enforce_print_safe_margin(path)
            after = inspect_candidate(path)

            self.assertGreaterEqual(margin["margin_x"], int(768 * 0.04))
            self.assertGreaterEqual(margin["margin_y"], int(1024 * 0.04))
            self.assertNotIn("safe_margin_too_busy", after["reasons"])
            self.assertTrue(after["content_qa"]["pass"])



if __name__ == "__main__":
    unittest.main()
