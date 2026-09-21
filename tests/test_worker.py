import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from worker.prompt_builder import build_edit_prompt, build_generation_prompt
from worker.qa import choose_best, inspect
from worker.workflows import image_edit, text_to_image


CFG = {
    "image": {"width": 768, "height": 1024},
    "generation": {"steps": 4},
    "model": {
        "unet": "flux-2-klein-4b-fp8.safetensors",
        "clip": "qwen_3_4b.safetensors",
        "vae": "flux2-vae.safetensors",
    },
}

PAGE = {
    "page_id": "I-01",
    "monster_name": "Kobold Warrior",
    "habitat": "Tight trapped stone corridor",
    "moment": "Cackling as a tripwire is triggered",
    "identity_rules": ["small reptilian humanoid", "long snout", "oversized spear"],
    "must_include": ["tripwire", "punji pit", "wall torch"],
    "must_avoid": ["cute reinterpretation"],
    "composition": "Portrait page; monster dominant.",
    "modify": {
        "preserve": ["pose", "spear", "pit"],
        "change": ["reduce wall detail", "more white space"],
        "avoid": ["stick figure"],
    },
}


class PromptTests(unittest.TestCase):
    def test_generation_prompt_contains_scene_and_house_rules(self):
        prompt = build_generation_prompt(PAGE)
        self.assertIn("Kobold Warrior", prompt)
        self.assertIn("tripwire", prompt)
        self.assertIn("pure black ink", prompt)
        self.assertIn("No color", prompt)

    def test_edit_prompt_separates_preserve_change_and_avoid(self):
        prompt = build_edit_prompt(PAGE, {"text": "simplify floor", "quick_tags": ["lighter interior lines"]})
        self.assertIn("PRESERVE", prompt)
        self.assertIn("reduce wall detail", prompt)
        self.assertIn("simplify floor", prompt)
        self.assertIn("lighter interior lines", prompt)
        self.assertIn("stick figure", prompt)


class WorkflowTests(unittest.TestCase):
    def test_text_to_image_uses_four_step_flux_stack(self):
        graph = text_to_image("test", 123, CFG, "test/output")
        classes = {node["class_type"] for node in graph.values()}
        self.assertIn("Flux2Scheduler", classes)
        self.assertIn("EmptyFlux2LatentImage", classes)
        self.assertIn("SaveImage", classes)
        scheduler = next(node for node in graph.values() if node["class_type"] == "Flux2Scheduler")
        self.assertEqual(scheduler["inputs"]["steps"], 4)

    def test_image_edit_uses_reference_latent(self):
        graph = image_edit("edit", 123, CFG, "test/output", "reference.png")
        classes = [node["class_type"] for node in graph.values()]
        self.assertEqual(classes.count("ReferenceLatent"), 2)
        load = next(node for node in graph.values() if node["class_type"] == "LoadImage")
        self.assertEqual(load["inputs"]["image"], "reference.png")


class QATests(unittest.TestCase):
    def test_clean_line_page_passes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.png"
            image = Image.new("RGB", (768, 1024), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((80, 80, 688, 944), outline="black", width=12)
            for y in range(180, 900, 80):
                draw.line((160, y, 608, y), fill="black", width=8)
            draw.ellipse((240, 240, 528, 600), outline="black", width=10)
            image.save(path)
            result = inspect(path)
            self.assertTrue(result["passed"], result["reasons"])

    def test_color_contamination_fails(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.png"
            image = Image.new("RGB", (768, 1024), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 300, 300), fill="red")
            draw.rectangle((80, 80, 688, 944), outline="black", width=12)
            image.save(path)
            result = inspect(path)
            self.assertFalse(result["passed"])
            self.assertTrue(any("color contamination" in r for r in result["reasons"]))

    def test_choose_best_ignores_failed_candidate(self):
        rows = [
            {"qa": {"passed": False, "score": 99}},
            {"qa": {"passed": True, "score": 80}},
            {"qa": {"passed": True, "score": 90}},
        ]
        self.assertIs(choose_best(rows), rows[2])


if __name__ == "__main__":
    unittest.main()
