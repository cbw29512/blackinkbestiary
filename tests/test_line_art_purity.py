import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from line_art_purity import classify_sample, purity_reasons


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


if __name__ == "__main__":
    unittest.main()
