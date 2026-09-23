import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWED_PAGE_KEYS = {
    "page_id",
    "order",
    "monster_spec_id",
    "moment",
    "archetype",
    "environment_profile_id",
    "environment_variant",
    "physicality",
}


class TomeIMinimalRecipeTests(unittest.TestCase):
    def test_all_fifty_pages_use_only_unique_recipe_fields(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        self.assertEqual(tome.get("page_contract"), "black-ink-page-v1")
        self.assertEqual(len(tome["pages"]), 50)

        for page in tome["pages"]:
            self.assertEqual(
                set(page),
                ALLOWED_PAGE_KEYS,
                f"{page.get('page_id')} contains non-recipe page data",
            )


if __name__ == "__main__":
    unittest.main()
