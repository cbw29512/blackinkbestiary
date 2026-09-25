import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from book_scaffold import build_book_plan, build_book_record
from replication_probe import run_replication_probe
from series_readiness import audit_series


class ReplicationReadinessTests(unittest.TestCase):
    def test_synthetic_tome_ix_scaffolds_from_generic_contracts(self):
        book = build_book_record(
            "TOME-IX-SYNTHETIC",
            "Synthetic Replication Probe",
            "A temporary theme used only to prove generic book scaffolding.",
            5,
            ["synthetic habitat"],
        )
        plan = build_book_plan(book, "IX")
        self.assertEqual(plan["target_pages"], 5)
        self.assertEqual([slot["page_id"] for slot in plan["slots"]], [
            "IX-01", "IX-02", "IX-03", "IX-04", "IX-05"
        ])
        self.assertEqual(book["page_contract"], "config/universal_page_contract.json")
        self.assertEqual(book["monster_contract"], "config/universal_monster_contract.json")
        self.assertEqual(book["environment_contract"], "config/universal_environment_contract.json")
        self.assertEqual(book["story_contract"], "config/universal_story_contract.json")

    def test_synthetic_runtime_probe_reaches_pre_gpu_boundary(self):
        report = run_replication_probe(ROOT)
        self.assertTrue(report["pass"], report["errors"])
        self.assertEqual(report["pages"], 3)
        self.assertTrue(all(report["stages"].values()))

    def test_replication_suite_includes_generic_book_assembly(self):
        self.assertTrue((ROOT / "art_pipeline" / "book_assembly.py").exists())
        self.assertTrue((ROOT / "scripts" / "assemble_book.py").exists())

    def test_existing_eight_book_series_still_passes_generic_audit(self):
        report = audit_series(ROOT)
        self.assertTrue(report["pass"])
        self.assertEqual(report["books_registered"], 8)


if __name__ == "__main__":
    unittest.main()
