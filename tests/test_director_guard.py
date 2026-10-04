import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from director_guard import (
    LEGACY_DIRECTOR_API_ENV,
    director_request_errors,
)


class DirectorGuardTests(unittest.TestCase):
    def write_manifest(self, root: Path, monster_name: str = "Flying Sword") -> None:
        try:
            data = root / "data"
            data.mkdir(parents=True, exist_ok=True)
            (data / "tome-I.json").write_text(
                json.dumps(
                    {
                        "pages": [
                            {
                                "page_id": "I-30",
                                "monster_name": monster_name,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
        except Exception:
            self.fail("Failed to build temporary canonical manifest fixture.")

    def test_external_director_api_requires_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_manifest(root)
            errors = director_request_errors(
                {"page_id": "I-30", "subject": "Flying Sword"},
                root=root,
                environ={},
            )
            self.assertTrue(any(LEGACY_DIRECTOR_API_ENV in item for item in errors))

    def test_director_subject_cannot_redefine_canonical_page_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_manifest(root)
            errors = director_request_errors(
                {"page_id": "I-30", "subject": "Otyugh"},
                root=root,
                environ={LEGACY_DIRECTOR_API_ENV: "1"},
            )
            self.assertTrue(any("disagrees with canonical" in item for item in errors))

    def test_matching_canonical_subject_is_allowed_after_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_manifest(root)
            errors = director_request_errors(
                {"page_id": "I-30", "subject": "Flying Sword"},
                root=root,
                environ={LEGACY_DIRECTOR_API_ENV: "1"},
            )
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
