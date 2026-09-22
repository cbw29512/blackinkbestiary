import struct
import tempfile
import unittest
import zlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from qa import inspect_candidate


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
                lambda x, y: 0 if (x % 64 in {0, 1, 2} or y % 96 in {0, 1}) else 255,
            )
            result = inspect_candidate(path)
            self.assertTrue(result["content_qa"]["pass"])
            self.assertNotIn("near_blank_page", result["reasons"])


if __name__ == "__main__":
    unittest.main()
