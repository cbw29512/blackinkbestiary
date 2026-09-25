import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from line_art_purity import classify_sample, purity_reasons
from png_content_qa import inspect_line_art


class LineArtPurityTests(unittest.TestCase):
    def test_black_and_white_are_not_midtone_or_chromatic(self):
        self.assertEqual(classify_sample(0, 0, 0), (False, False))
        self.assertEqual(classify_sample(255, 255, 255), (False, False))

    def test_gray_shading_is_midtone(self):
        self.assertEqual(classify_sample(160, 160, 160), (True, False))

    def test_color_is_chromatic(self):
        self.assertEqual(classify_sample(220, 80, 80), (True, True))

    def test_excessive_midtone_fails(self):
        _, _, reasons = purity_reasons(9, 0, 100)
        self.assertIn("excessive_grayscale_or_shading", reasons)

    def test_trace_antialiasing_stays_tolerated(self):
        _, _, reasons = purity_reasons(8, 0, 100)
        self.assertNotIn("excessive_grayscale_or_shading", reasons)

    def test_meaningful_color_contamination_fails(self):
        _, _, reasons = purity_reasons(0, 1, 100)
        self.assertIn("color_pixels_detected", reasons)


    def test_inspector_reports_purity_metrics(self):
        import struct
        import tempfile
        import zlib

        def chunk(kind, payload):
            checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)

        ihdr = struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0)
        scanline = bytes([0, 0, 0, 0, 255, 255, 255])
        signature = bytes([137, 80, 78, 71, 13, 10, 26, 10])
        raw = signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(scanline)) + chunk(b"IEND", b"")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "line-art.png"
            path.write_bytes(raw)
            report = inspect_line_art(path)
        self.assertEqual(report["midtone_ratio"], 0.0)
        self.assertEqual(report["chromatic_ratio"], 0.0)
        self.assertTrue(report["pass"])

if __name__ == "__main__":
    unittest.main()
