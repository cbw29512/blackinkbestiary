import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from environment_catalog import environment_fingerprint, resolve_environment_profile
from prompt_builder import build_prompt
from quality_system import coloring_page_directives


class EnvironmentCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))

    def test_every_environment_catalog_profile_is_complete(self):
        for path in sorted((ROOT / "data" / "environment_families").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(payload.get("family_id"), path)
            self.assertTrue(payload.get("profiles"), path)
            for profile_id, profile in payload["profiles"].items():
                self.assertTrue(profile_id, path)
                self.assertTrue(profile.get("name"), profile_id)
                self.assertTrue(profile.get("description"), profile_id)
                self.assertGreaterEqual(len(profile.get("visual_cues") or []), 3, profile_id)
                self.assertTrue(profile.get("colorable_forms"), profile_id)
                self.assertTrue(profile.get("must_avoid"), profile_id)

    def test_all_tome_i_pages_resolve_specific_environment_profiles(self):
        self.assertEqual(len(self.tome["pages"]), 50)
        for page in self.tome["pages"]:
            profile = resolve_environment_profile(page["environment_profile_id"])
            self.assertTrue(profile["description"])
            self.assertGreaterEqual(len(profile["visual_cues"]), 3)
            self.assertTrue((page.get("environment_variant") or {}).get("landmark"))
            self.assertTrue((page.get("environment_variant") or {}).get("framing"))
            self.assertTrue((page.get("environment_variant") or {}).get("interaction"))

    def test_tome_i_background_fingerprints_are_unique(self):
        fingerprints = [environment_fingerprint(page) for page in self.tome["pages"]]
        self.assertEqual(len(fingerprints), len(set(fingerprints)))

    def test_cave_and_ocean_catalogs_have_real_variation(self):
        expected = [
            "underground.limestone-drip-cave",
            "underground.basalt-lava-tube",
            "underground.talus-boulder-cave",
            "underground.sea-cave",
            "ocean.kelp-forest",
            "ocean.deep-coral-garden",
            "ocean.shipwreck-field",
            "ocean.hydrothermal-vent-field",
            "ocean.seamount-slope",
        ]
        profiles = [resolve_environment_profile(profile_id) for profile_id in expected]
        self.assertEqual(len({profile["name"] for profile in profiles}), len(expected))

    def test_prompt_contains_environment_variant_and_large_colorable_forms(self):
        page = next(page for page in self.tome["pages"] if page["page_id"] == "I-47")
        text = build_prompt(page)
        self.assertIn("Crystal Cavern", text)
        self.assertIn("LARGE COLORABLE ENVIRONMENT FORMS", text)
        self.assertIn("UNIQUE BACKGROUND LANDMARK", text)
        self.assertIn("MONSTER / ENVIRONMENT INTERACTION", text)

    def test_coloring_standard_prioritizes_large_simple_regions(self):
        directives = " ".join(coloring_page_directives(ROOT)).lower()
        self.assertIn("large", directives)
        self.assertIn("tiny", directives)
        self.assertIn("broad", directives)


if __name__ == "__main__":
    unittest.main()
