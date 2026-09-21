import random
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from qa import inspect_candidate


class ColoringPageQATests(unittest.TestCase):
    def _path(self, tmp, name):
        return Path(tmp) / name

    def test_open_black_line_art_passes_and_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._path(tmp, "line-art.png")
            image = Image.new("RGB", (768, 1024), "white")
            draw = ImageDraw.Draw(image)
            rng = random.Random(7)
            for _ in range(850):
                x = rng.randrange(20, 748)
                y = rng.randrange(20, 1004)
                length = rng.randrange(6, 45)
                draw.line((x, y, min(747, x + length), y), fill="black", width=2)
            image.save(path)
            report = inspect_candidate(path)
            self.assertTrue(report["pass"], report)
            self.assertGreater(report["metrics"]["white_fraction"], 0.65)
            self.assertLess(report["metrics"]["color_fraction"], 0.005)
            self.assertGreater(report["style_score"], 60)

    def test_gray_wash_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._path(tmp, "gray.png")
            Image.new("RGB", (768, 1024), (150, 150, 150)).save(path)
            report = inspect_candidate(path)
            self.assertFalse(report["pass"])
            self.assertIn("too_much_grayscale_or_shading", report["reasons"])

    def test_color_page_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._path(tmp, "color.png")
            Image.new("RGB", (768, 1024), (240, 80, 80)).save(path)
            report = inspect_candidate(path)
            self.assertFalse(report["pass"])
            self.assertIn("too_much_color", report["reasons"])


if __name__ == "__main__":
    unittest.main()
