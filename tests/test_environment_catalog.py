import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from environment_catalog import environment_fingerprint, resolve_environment_profile
from environment_components import assembly_fingerprint, assemble_environment_palette
from environment_assembly import infer_overlays
from environment_engine_audit import audit_environment_engine
from environment_spatial import resolve_spatial_envelope
from environment_variation import load_variation_registry
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

    def test_every_profile_resolves_environment_identity(self):
        for page in self.tome["pages"]:
            profile = resolve_environment_profile(page["environment_profile_id"])
            identity = profile["resolved_identity"]
            self.assertTrue(identity["spatial_type"], page["page_id"])
            self.assertTrue(identity["material_language"], page["page_id"])
            self.assertTrue(identity["identity_markers"], page["page_id"])
            self.assertTrue(identity["spatial_read"], page["page_id"])

    def test_i09_reads_as_low_dungeon_crawlway_not_generic_hallway(self):
        page = next(page for page in self.tome["pages"] if page["page_id"] == "I-09")
        profile = resolve_environment_profile(page["environment_profile_id"])
        identity = profile["resolved_identity"]
        self.assertIn("dungeon service crawlway", identity["spatial_type"])
        self.assertIn("stone block walls", identity["material_language"])
        self.assertTrue(any("sconce" in item for item in identity["identity_markers"]))
        self.assertIn("generic hallway", identity["spatial_read"])

        text = build_prompt(page)
        self.assertIn("ENVIRONMENT SPATIAL TYPE", text)
        self.assertIn("ENVIRONMENT MATERIAL LANGUAGE", text)
        self.assertIn("ENVIRONMENT IDENTITY MARKERS", text)
        self.assertIn("UNIVERSAL ENVIRONMENT IDENTITY RULES", text)
        self.assertIn("flagstone floor", text)

    def test_i01_resolves_to_narrow_built_corridor_envelope(self):
        page = next(page for page in self.tome["pages"] if page["page_id"] == "I-01")
        profile = resolve_environment_profile(page["environment_profile_id"])
        envelope = resolve_spatial_envelope(profile)
        text = build_prompt(page)
        self.assertEqual(envelope["envelope_id"], "narrow_built_corridor")
        self.assertIn("length visibly exceeds width", envelope["proportions"])
        self.assertIn("SPACE ENVELOPE: narrow_built_corridor", text)
        self.assertIn("two side boundaries", text)
        self.assertIn("square room", text)

    def test_every_environment_profile_resolves_a_spatial_envelope(self):
        count = 0
        for path in sorted((ROOT / "data" / "environment_families").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for profile_id in payload.get("profiles", {}):
                count += 1
                profile = resolve_environment_profile(profile_id)
                envelope = resolve_spatial_envelope(profile)
                self.assertTrue(envelope["plan_shape"], profile_id)
                self.assertTrue(envelope["must_show"], profile_id)
                self.assertTrue(envelope["must_not_drift"], profile_id)
        self.assertGreaterEqual(count, 70)
    def test_i02_shrine_keeper_stays_limestone_cave_not_dungeon_corridor(self):
        page = next(page for page in self.tome["pages"] if page["page_id"] == "I-02")
        palette = assemble_environment_palette(page, ROOT)
        text = build_prompt(page)
        envelope = resolve_spatial_envelope(resolve_environment_profile(page["environment_profile_id"]))
        self.assertEqual(envelope["envelope_id"], "natural_cavern")
        self.assertIn("natural", palette["contexts"])
        self.assertIn("cave", palette["contexts"])
        self.assertIn("limestone", palette["contexts"])
        self.assertIn("HABITAT: Limestone Drip Cave", text)
        self.assertIn("PAGE ENVIRONMENT AUTHORITY", text)
        self.assertIn("dragon skull", text.lower())
        self.assertIn("coin", text.lower())
        self.assertIn("ACTIVE ENVIRONMENT OVERLAY RULES", text)
        self.assertIn("PAGE RECIPE LOCK", text)
        self.assertIn("low flowstone altar with dragon skull and coin offerings", text)
        self.assertIn("raises a coin toward the natural rock shrine", text)
        self.assertNotIn("CANONICAL ENVIRONMENT FIT", text)

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

    def test_every_environment_family_has_deep_variation_pools(self):
        registry = load_variation_registry()
        self.assertEqual(len(registry["families"]), 8)
        for family_id, family in registry["families"].items():
            for key in (
                "geometry_pool",
                "landmark_pool",
                "prop_pool",
                "interaction_pool",
                "anti_repetition_rules",
            ):
                self.assertGreaterEqual(len(family[key]), 4, f"{family_id}:{key}")

    def test_v3_component_engine_scales_across_every_environment_family(self):
        report = audit_environment_engine(ROOT)
        self.assertTrue(report["pass"], report["errors"])
        self.assertEqual(report["environment_families"], 8)
        self.assertEqual(report["component_catalogs"], 8)
        self.assertGreaterEqual(report["total_components"], 800)
        self.assertGreaterEqual(report["overlay_count"], 8)

    def test_prompt_uses_selected_palette_not_entire_component_library(self):
        page = next(page for page in self.tome["pages"] if page["page_id"] == "I-03")
        text = build_prompt(page)
        self.assertIn("SELECTED SPATIAL ARCHETYPES", text)
        self.assertIn("SELECTED PRIMARY SURFACES", text)
        self.assertIn("SELECTED LIGHTING FEATURES", text)
        self.assertIn("ENVIRONMENT PALETTE RULE", text)
        self.assertNotIn("FAMILY GEOMETRY VARIATION POOL", text)
        self.assertIn(page["environment_variant"]["landmark"], text)

    def test_i01_requires_literal_wall_mount_and_readable_tripwire(self):
        page = next(page for page in self.tome["pages"] if page["page_id"] == "I-01")
        text = build_prompt(page)
        self.assertIn("REQUIRED OBJECT PHYSICAL RULES", text)
        self.assertIn("visibly attach to the wall", text)
        self.assertIn("never draw it as a freestanding floor torch", text)
        self.assertIn("tripwire must visibly cross the traversable path", text)
        self.assertIn("cause-and-effect reads instantly", text)
    def test_trap_page_automatically_receives_hazard_and_trap_overlay(self):
        page = next(page for page in self.tome["pages"] if page["page_id"] == "I-01")
        palette = assemble_environment_palette(page, ROOT)
        self.assertIn("hazards", palette["components"])
        self.assertIn("lighting_features", palette["components"])
        self.assertIn("ground_planes", palette["components"])
        self.assertIn("trap", palette["contexts"])
        self.assertTrue(any(item["overlay_id"] == "trap_zone" for item in palette["overlays"]))

    def test_environment_component_assembly_is_deterministic_and_unique(self):
        first = [assembly_fingerprint(page, ROOT) for page in self.tome["pages"]]
        second = [assembly_fingerprint(page, ROOT) for page in self.tome["pages"]]
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(set(first)))

    def test_prompt_contains_environment_variant_and_large_colorable_forms(self):
        page = next(page for page in self.tome["pages"] if page["page_id"] == "I-47")
        text = build_prompt(page)
        self.assertIn("Crystal Cavern", text)
        self.assertIn("LARGE COLORABLE ENVIRONMENT FORMS", text)
        self.assertIn("UNIQUE BACKGROUND LANDMARK", text)
        self.assertIn("MONSTER / ENVIRONMENT INTERACTION", text)

    def test_reference_composition_keeps_monster_large_and_centered(self):
        standard = json.loads(
            (ROOT / "config" / "coloring_page_standard.json").read_text(encoding="utf-8")
        )
        ref = standard["reference_composition"]
        self.assertEqual(ref["monster_page_height_target"], [0.6, 0.75])
        self.assertIn("centered", ref["placement"])
        self.assertIn("full or nearly full silhouette", ref["placement"])
        self.assertEqual(ref["environment_major_forms"], [2, 4])

    def test_coloring_standard_prioritizes_large_simple_regions(self):
        directives = " ".join(coloring_page_directives(ROOT)).lower()
        self.assertIn("large", directives)
        self.assertIn("tiny", directives)
        self.assertIn("broad", directives)

    def test_explicit_environment_roles_are_authoritative(self):
        page = next(page for page in self.tome["pages"] if page["page_id"] == "I-01")
        profile = resolve_environment_profile(page["environment_profile_id"])
        sample = dict(page)
        sample["environment_roles"] = ["laboratory", "trap_zone"]
        overlays = infer_overlays(sample, profile, ROOT)
        self.assertEqual([item["overlay_id"] for item in overlays[:2]], ["laboratory", "trap_zone"])

    def test_specific_inferred_role_beats_broad_registry_order(self):
        page = next(page for page in self.tome["pages"] if page["page_id"] == "I-01")
        profile = resolve_environment_profile(page["environment_profile_id"])
        sample = dict(page)
        sample["moment"] = "A creature guards a working alchemical laboratory workshop."
        overlays = infer_overlays(sample, profile, ROOT)
        ids = [item["overlay_id"] for item in overlays]
        self.assertIn("laboratory", ids)
        self.assertLess(ids.index("laboratory"), len(ids))


if __name__ == "__main__":
    unittest.main()
