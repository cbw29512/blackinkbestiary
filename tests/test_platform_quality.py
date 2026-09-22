import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from manifest_validation import validate_manifest
from quality_system import (
    archetype_directive,
    environment_approval_checks,
    environment_directives,
    expand_defect_tags,
    recommended_action,
)
from studio_config import active_book_paths


class PlatformQualityTests(unittest.TestCase):
    def test_active_book_paths_are_project_local(self):
        paths = active_book_paths(ROOT)
        self.assertEqual(paths["manifest"], ROOT / "data" / "tome-I.json")
        self.assertEqual(paths["state"], ROOT / "data" / "production-state.json")
        for path in paths.values():
            self.assertTrue(path == ROOT or ROOT in path.parents)

    def test_defect_tags_expand_to_actionable_directives(self):
        directives = expand_defect_tags(
            ROOT,
            ["story beat unclear", "required prop missing", "pose too stiff"],
        )
        self.assertEqual(len(directives), 3)
        self.assertTrue(any("cause-and-effect" in item for item in directives))
        self.assertTrue(any("missing required prop" in item for item in directives))
        self.assertTrue(any("gesture" in item for item in directives))

    def test_environment_standard_is_global_and_actionable(self):
        directives = environment_directives(ROOT)
        checks = environment_approval_checks(ROOT)
        self.assertTrue(any("co-equal storytelling pillars" in item for item in directives))
        self.assertTrue(any("two to four" in item.lower() for item in directives))
        self.assertTrue(any("without reading the caption" in item for item in checks))

    def test_environment_defects_route_correctly(self):
        self.assertEqual(recommended_action(ROOT, ["environment identity weak"]), "modify")
        self.assertEqual(recommended_action(ROOT, ["environment generic"]), "modify")
        self.assertEqual(recommended_action(ROOT, ["wrong environment"]), "regenerate")

    def test_composition_failure_recommends_regenerate(self):
        self.assertEqual(recommended_action(ROOT, ["composition wrong"]), "regenerate")
        self.assertEqual(recommended_action(ROOT, ["less detail"]), "modify")

    def test_archetype_rule_is_page_driven(self):
        page = {"archetype": "trap_scene"}
        text = archetype_directive(ROOT, page)
        self.assertIn("cause-and-effect", text)
        self.assertIn("trap trigger", text)

    def test_active_manifest_passes_platform_validation(self):
        paths = active_book_paths(ROOT)
        tome = json.loads(paths["manifest"].read_text(encoding="utf-8"))
        errors = validate_manifest(ROOT, tome, ROOT / "data" / "monsters")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
