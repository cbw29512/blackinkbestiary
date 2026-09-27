import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from book_assembly import (
    assemble_pdf,
    attribution_lines,
    binding_side_for_page,
    locked_page_paths,
)


def _chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def _write_gray_png(path: Path, width: int = 16, height: int = 20) -> None:
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.append(0 if (x == width // 2 or y == height // 2) else 255)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )


class BookAssemblyTests(unittest.TestCase):
    def test_pdf_assembly_is_deterministic_and_ordered(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "one.png"
            second = root / "two.png"
            _write_gray_png(first)
            _write_gray_png(second)

            a = root / "a.pdf"
            b = root / "b.pdf"
            report_a = assemble_pdf([first, second], a, title="Synthetic Tome")
            report_b = assemble_pdf([first, second], b, title="Synthetic Tome")

            self.assertEqual(report_a["pages"], 2)
            self.assertEqual(report_a["sha256"], report_b["sha256"])
            self.assertEqual(a.read_bytes(), b.read_bytes())
            payload = a.read_bytes()
            self.assertTrue(payload.startswith(b"%PDF-1.4"))
            self.assertIn(b"/Count 2", payload)
            self.assertIn(b"/MediaBox [0 0 612 792]", payload)

    def test_optional_credits_page_is_deterministic_and_appended_last(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "one.png"
            _write_gray_png(first)
            credits = [
                "Legal Attribution",
                "",
                "System Reference Document 5.2.1",
                "By Wizards of the Coast LLC",
            ]

            a = root / "credits-a.pdf"
            b = root / "credits-b.pdf"
            report_a = assemble_pdf(
                [first],
                a,
                title="Synthetic Tome",
                credits_lines=credits,
            )
            report_b = assemble_pdf(
                [first],
                b,
                title="Synthetic Tome",
                credits_lines=credits,
            )

            self.assertEqual(report_a["art_pages"], 1)
            self.assertEqual(report_a["pages"], 2)
            self.assertTrue(report_a["credits_page"])
            self.assertEqual(report_a["sha256"], report_b["sha256"])
            payload = a.read_bytes()
            self.assertIn(b"/Count 2", payload)
            self.assertIn(b"Legal Attribution", payload)
            self.assertIn(b"System Reference Document 5.2.1", payload)
            # The image page object is emitted before the credits page objects.
            self.assertLess(payload.index(b"/Subtype /Image"), payload.index(b"Legal Attribution"))

    def test_project_attribution_metadata_supplies_required_credit_elements(self):
        lines = attribution_lines(ROOT)
        joined = "\n".join(lines)
        self.assertIn("System Reference Document 5.2.1", joined)
        self.assertIn("Wizards of the Coast LLC", joined)
        self.assertIn("https://www.dndbeyond.com/srd", joined)
        self.assertIn("Creative Commons Attribution 4.0 International", joined)
        self.assertIn(
            "https://creativecommons.org/licenses/by/4.0/legalcode",
            joined,
        )

    def test_binding_side_alternates_for_interior_pages(self):
        self.assertEqual(binding_side_for_page(1), "left")
        self.assertEqual(binding_side_for_page(2), "right")
        self.assertEqual(binding_side_for_page(3), "left")
        self.assertEqual(binding_side_for_page(4), "right")

    def test_locked_page_gate_passes_page_specific_binding_side_to_kdp_qa(self):
        manifest = {
            "total_pages": 2,
            "pages": [
                {"page_id": "X-01", "order": 1},
                {"page_id": "X-02", "order": 2},
            ],
        }
        state = {
            "pages": {
                "X-01": {
                    "status": "locked",
                    "approved_image_path": "approved/one.png",
                },
                "X-02": {
                    "status": "locked",
                    "approved_image_path": "approved/two.png",
                },
            }
        }
        calls = []

        def fake_inspect(path, *, binding_side=None):
            calls.append((Path(path).name, binding_side))
            return {"pass": True, "reasons": []}

        with tempfile.TemporaryDirectory() as td, patch(
            "book_assembly.inspect_kdp_export",
            side_effect=fake_inspect,
        ):
            paths = locked_page_paths(Path(td), manifest, state)

        self.assertEqual(len(paths), 2)
        self.assertEqual(calls, [("one.png", "left"), ("two.png", "right")])

    def test_locked_book_gate_rejects_unlocked_page_before_pdf_work(self):
        manifest = {
            "total_pages": 1,
            "pages": [{"page_id": "X-01", "order": 1}],
        }
        state = {"pages": {"X-01": {"status": "queued"}}}
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(RuntimeError, "page is not locked"):
                locked_page_paths(Path(td), manifest, state)


if __name__ == "__main__":
    unittest.main()
