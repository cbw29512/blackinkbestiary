import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

KNOWN_SCENE_LEAKS = (
    "earth burst reads clearly",
    "petrified mouse reads clearly",
    "crystal coil composition",
    "soil-cutting movement",
    "wall-hook disguise",
    "old bone interaction",
    "mine setting",
    "water ripples support movement",
    "rubble concealment",
    "garbage setting",
    "maw dominates the page",
    "tunnel geometry",
    "ruined weapons show corrosion",
    "sleeping target",
    "gate remains secondary",
    "final-page composition",
    "bow aiming downward",
    "corridor-filling",
    "pedestal display origin",
    "visible phylactery object",
)


def monster_identity_text(payload: dict) -> str:
    visual = payload.get("visual_overrides") or payload.get("visual_identity") or {}
    parts = [
        visual.get("core_identity"),
        visual.get("silhouette"),
        visual.get("head_features"),
        visual.get("body_shape"),
        visual.get("surface"),
        *(visual.get("signature_gear") or []),
        *(visual.get("must_keep") or []),
        *(payload.get("accuracy_checks") or []),
        *(payload.get("variant_traits") or []),
    ]
    return " ".join(str(item or "").lower() for item in parts)


class MonsterIdentityScopeTests(unittest.TestCase):
    def test_known_tome_i_scene_leaks_are_absent_from_monster_identity(self):
        for path in sorted((ROOT / "data" / "monsters").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            text = monster_identity_text(payload)
            for marker in KNOWN_SCENE_LEAKS:
                self.assertNotIn(marker, text, f"{path.stem}: leaked scene marker {marker!r}")

    def test_legacy_accuracy_checks_avoid_page_and_scene_approval_language(self):
        forbidden = ("matches scene", "final-page", "the page", "composition feels")
        for path in sorted((ROOT / "data" / "monsters").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("family_profile") and int(payload.get("schema_version") or 1) >= 3:
                continue
            checks = " ".join(str(item).lower() for item in payload.get("accuracy_checks") or [])
            for marker in forbidden:
                self.assertNotIn(marker, checks, f"{path.stem}: {marker}")


if __name__ == "__main__":
    unittest.main()
