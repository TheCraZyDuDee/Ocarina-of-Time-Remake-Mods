"""Test the private NSO unpacking workflow without any game files or keys."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

path = (Path(__file__).resolve().parents[1] / "mods" / "fps" /
        "research" / "true-dynamic" / "private_nso_inspection_image.py")
spec = importlib.util.spec_from_file_location("private_nso_inspection_image", path)
reader = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reader
spec.loader.exec_module(reader)


def synthetic(compressed=False, zbic=False):
    data = bytearray(b'\0' * 0x100)
    data[:4] = b'NSO0'
    data[0x40:0x54] = bytes.fromhex('E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348')
    flags = ((0b111 if compressed else 0) | (0x80 if zbic else 0))
    struct.pack_into('<I', data, 0xC, flags)
    offset = 0x100
    for i in range(3):
        value = bytes([65+i]) * (16+i)
        raw = b'ZBIC' + value if zbic else value
        struct.pack_into('<III', data, 0x10+i*16, offset, 0x20*i, len(value))
        struct.pack_into('<I', data, 0x60+i*4, len(raw))
        data[0xA0+32*i:0xC0+32*i] = hashlib.sha256(value).digest()
        data.extend(raw)
        offset += len(raw)
    return bytes(data)


class SyntheticInspectionTests(unittest.TestCase):
    def test_uncompressed(self):
        image, build = reader.make_inspection_image(synthetic())
        self.assertEqual(len(image), 0x100+0x40+18)
        self.assertEqual(image[0x100:0x110], b'A'*16)
        self.assertEqual(image[0x120:0x131], b'B'*17)
        self.assertTrue(build.startswith('E0F3'))

    def test_zbic_mock(self):
        def decoder(name):
            if name == 'zbic':
                return types.SimpleNamespace(decompress=lambda raw: raw[4:])
            raise AssertionError(name)
        with patch.object(reader.importlib, 'import_module', decoder):
            image, _ = reader.make_inspection_image(synthetic(True, True))
            self.assertEqual(image[0x100:0x110], b'A'*16)

    def test_invalid_digest(self):
        data = bytearray(synthetic())
        data[-1] ^= 3
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            reader.make_inspection_image(bytes(data))

    def test_missing_zbic_is_clear(self):
        with patch.object(reader.importlib, 'import_module', side_effect=ImportError()):
            with self.assertRaisesRegex(RuntimeError, 'pip install zbic'):
                reader.make_inspection_image(synthetic(True, True))

    def test_invalid_offset_and_header(self):
        data = bytearray(synthetic())
        struct.pack_into('<I', data, 0x10+2*16, 0xFFFFF)
        with self.assertRaisesRegex(ValueError, 'descriptor'):
            reader.make_inspection_image(bytes(data))
        with self.assertRaises(ValueError):
            reader.inspect_header(b'NSO0')

    def test_not_a_runnable_nso(self):
        image, _ = reader.make_inspection_image(synthetic())
        self.assertEqual(image[0xC:0x10], synthetic()[0xC:0x10])
        self.assertEqual(image[:4], b'NSO0')


if __name__ == '__main__':
    unittest.main()
