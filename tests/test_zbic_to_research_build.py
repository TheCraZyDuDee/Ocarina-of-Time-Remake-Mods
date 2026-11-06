"""Synthetic-only tests of the original-ZBIC -> inspection -> IPS pipeline."""
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1] / "mods/fps/research/true-dynamic"
sys.path.insert(0, str(ROOT))
import build_isolated_from_original_zbic as pipeline
import inspection_image_validation as validator
import isolated_step_research_builder as builder
import private_nso_inspection_image as reader

CONFIG = {"guard": 0x100, "present": 0x104, "delta_hook": 0x200}
CAVE = 0x300
WORDS = (0xD503201F,) * 16


def fake_original_nso():
    text = bytearray(b"\x00" * 0x3c0)
    for off, instr in (
        (CONFIG["guard"], builder.ORIGINAL_GUARD),
        (CONFIG["present"], builder.ORIGINAL_PRESENT),
        (CONFIG["delta_hook"]-4, builder.DIV_NUMERATOR),
        (CONFIG["delta_hook"], builder.ORIGINAL_DIV),
        (CONFIG["delta_hook"]+4, builder.DIV_NEXT_BRANCH),
    ):
        struct.pack_into("<I", text, off, instr)
    segments = [bytes(text), b"B" * 0x40, b"C" * 0x50]
    memory_offsets = [0, 0x400, 0x480]
    data = bytearray(b"\x00" * 0x100)
    data[:4] = b"NSO0"
    data[0x40:0x54] = bytes.fromhex(pipeline.BUILD)
    struct.pack_into("<I", data, 0xC, 0x87)  # ZBIC and 3 compressed sections
    for i, (chunk, mem) in enumerate(zip(segments, memory_offsets)):
        start = len(data)
        packed = b"ZBIC" + chunk  # synthetic reversible decoder ONLY
        struct.pack_into("<III", data, 0x10 + i*16, start, mem, len(chunk))
        struct.pack_into("<I", data, 0x60 + 4*i, len(packed))
        data[0xA0 + 32*i:0xC0 + 32*i] = hashlib.sha256(chunk).digest()
        data.extend(packed)
    return bytes(data)


class ZBICPipelineTests(unittest.TestCase):
    def fake_zbic(self):
        def import_mock(name):
            if name == "zbic":
                return types.SimpleNamespace(decompress=lambda data: data[4:])
            raise ImportError(name)
        return patch.object(reader.importlib, "import_module", side_effect=import_mock)

    def test_three_verified_decoded_sections_at_memory_offsets(self):
        with self.fake_zbic():
            image, name = reader.make_inspection_image(fake_original_nso())
        self.assertEqual(name, pipeline.BUILD)
        self.assertEqual(image[0x100+0x400:0x100+0x440], b"B"*0x40)
        self.assertEqual(image[0x100+0x480:0x100+0x4d0], b"C"*0x50)
        valid = validator.validate_inspection_image(image, pipeline.BUILD)
        self.assertEqual([d["section"] for d in valid],
                         ["text", "rodata", "data"])

    def test_rejects_compressed_original_as_an_inspection_image(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            validator.validate_inspection_image(fake_original_nso(), pipeline.BUILD)

    def test_rejects_corrupted_decoded_segment(self):
        with self.fake_zbic():
            image, _ = reader.make_inspection_image(fake_original_nso())
        damaged = bytearray(image)
        damaged[0x100+0x400] ^= 4
        with self.assertRaisesRegex(ValueError, "rodata decoded section"):
            validator.validate_inspection_image(bytes(damaged), pipeline.BUILD)

    def test_wrong_build_rejected(self):
        with self.fake_zbic():
            image, _ = reader.make_inspection_image(fake_original_nso())
        with self.assertRaisesRegex(ValueError, "build ID"):
            validator.validate_inspection_image(image, "33FA")

    def test_end_to_end_produces_only_private_ips_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp)/"main"
            original.write_bytes(fake_original_nso())
            output = Path(tmp)/"first-test.zip"
            with self.fake_zbic(), \
                 patch.object(builder, "CONFIG", CONFIG), \
                 patch.object(builder.previous, "assemble", return_value=WORDS), \
                 patch.object(builder.previous, "find_caves",
                              side_effect=lambda data, hook, length: [(CAVE, length)]):
                result = pipeline.create_from_original_zbic(original, output)
            self.assertEqual(result["build_id"], pipeline.BUILD)
            self.assertEqual(result["ips_instruction_records"], len(WORDS)+2)
            self.assertEqual(len(result["verified_segment_names"]), 3)
            with zipfile.ZipFile(output) as package:
                self.assertEqual(package.testzip(), None)
                self.assertEqual(len(package.namelist()), 2)
                self.assertFalse(any("nso" in path.lower() for path in package.namelist()))
                self.assertTrue(any(path.endswith(".ips") for path in package.namelist()))
            with self.assertRaisesRegex(ValueError, "already exists"):
                pipeline.create_from_original_zbic(original, output)

    def test_corrupt_original_hash_never_produces_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp)/"main"
            data = bytearray(fake_original_nso())
            # Corrupt compressed (synthetic) text section after original hash.
            file_off = struct.unpack_from("<I", data, 0x10)[0]
            data[file_off+5] ^= 2
            original.write_bytes(data)
            output = Path(tmp)/"invalid.zip"
            with self.fake_zbic(), patch.object(builder, "CONFIG", CONFIG):
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    pipeline.create_from_original_zbic(original, output)
            self.assertFalse(output.exists())

    def test_no_pkg_fails_clear_without_mod_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/"main"
            source.write_bytes(fake_original_nso())
            output = Path(tmp)/"output.zip"
            with patch.object(reader.importlib, "import_module", side_effect=ImportError()):
                with self.assertRaisesRegex(RuntimeError, "pip install zbic"):
                    pipeline.create_from_original_zbic(source, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
