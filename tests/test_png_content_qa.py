import struct
import tempfile
import unittest
import zlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from qa import inspect_candidate
from png_content_qa import enforce_print_safe_margin


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
