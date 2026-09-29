import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(ROOT / "art_pipeline"))
sys.path.insert(0, str(ROOT / "scripts"))

from page_contract import resolve_page_spec
from scene_scaffold import render_scene_scaffold, scaffold_enabled, scaffold_prompt_prefix
import generation_fingerprint as gf
import generate_test_gallery as gallery


class SceneScaffoldTests(unittest.TestCase):
    def i01(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        raw = next(page for page in tome["pages"] if page["page_id"] == "I-01")
        return resolve_page_spec(raw, ROOT)

    def test_i01_declares_hard_geometry_scaffold(self):
        page = self.i01()
        self.assertTrue(scaffold_enabled(page))
        cfg = page["scene_scaffold"]
        kinds = [row["type"] for row in cfg["primitives"]]
        self.assertIn("archway", kinds)
        self.assertIn("pit", kinds)
        self.assertIn("connector", kinds)
        connector = next(row for row in cfg["primitives"] if row["type"] == "connector")
        self.assertEqual(connector["anchors"], ["left wall ring", "right wall ring"])
        self.assertNotEqual(connector["from"], connector["to"])

    def test_i01_scaffold_renders_real_geometry(self):
        page = self.i01()
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "i01-scaffold.png"
            rendered = render_scene_scaffold(page, output, width=768, height=1024)
            self.assertEqual(rendered, output)
            self.assertTrue(output.exists())
            payload = output.read_bytes()
            self.assertTrue(payload.startswith(b"\x89PNG\r\n\x1a\n"))
            width, height = struct.unpack(">II", payload[16:24])
            self.assertEqual((width, height), (768, 1024))

            offset = 8
            idat = bytearray()
            while offset < len(payload):
                length = struct.unpack(">I", payload[offset:offset + 4])[0]
                kind = payload[offset + 4:offset + 8]
                data = payload[offset + 8:offset + 8 + length]
                if kind == b"IDAT":
                    idat.extend(data)
                offset += 12 + length
                if kind == b"IEND":
                    break
            raw = zlib.decompress(bytes(idat))
            stride = 769
            self.assertEqual(len(raw), 1024 * stride)

            connector = next(
                row for row in page["scene_scaffold"]["primitives"]
                if row["type"] == "connector"
            )
            for point in (connector["from"], connector["to"]):
                x = round(point[0] * 768)
                y = round(point[1] * 1024)
                black_found = False
                for yy in range(max(0, y - 8), min(1024, y + 9)):
                    row = raw[yy * stride + 1:(yy + 1) * stride]
                    for xx in range(max(0, x - 8), min(768, x + 9)):
                        if row[xx] == 0:
                            black_found = True
                            break
                    if black_found:
                        break
                self.assertTrue(black_found)

    def test_scaffold_prompt_forbids_blank_openings_and_creature_attached_tripwire(self):
        prompt = scaffold_prompt_prefix(self.i01()).lower()
        self.assertIn("empty white void", prompt)
        self.assertIn("left wall ring", prompt)
        self.assertIn("right wall ring", prompt)
        self.assertIn("never on the creature", prompt)
        self.assertIn("kobold", prompt)

    def test_scaffold_is_part_of_generation_fingerprint_authority(self):
        self.assertIn("art_pipeline/scene_scaffold.py", gf.GENERATION_EXECUTION_FILES)
        self.assertIn("scene_scaffold", gf.PAGE_AUTHORITY_FIELDS)

    def test_non_scaffold_page_keeps_normal_text_to_image_path(self):
        page = {"page_id": "X-01"}
        expected = Path("normal-workflow.json")
        with patch.object(gallery, "prepare", return_value=expected) as normal:
            result = gallery.prepare_from_authority(
                object(), object(), {}, page, 123, 1, None
            )
        self.assertEqual(result, expected)
        normal.assert_called_once()

    def test_generator_routes_fresh_scaffolded_pages_through_image_guidance(self):
        source = (ROOT / "scripts" / "generate_test_gallery.py").read_text(encoding="utf-8")
        self.assertIn("def prepare_from_authority(", source)
        self.assertIn("render_scene_scaffold(", source)
        self.assertIn("single traced draw", source)
        self.assertGreaterEqual(source.count("prepare_from_authority("), 3)
        self.assertIn("blackink-scaffolds", source)


if __name__ == "__main__":
    unittest.main()
