"""Synthetic IPS32 tests for reproducibility of tester-successful E0F3 V10."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SRC = Path(__file__).resolve().parents[1] / "mods/fps/research/true-dynamic"
sys.path.insert(0, str(SRC))
import reproduce_v10_ips_from_v9_archive as mod

FAKE_HELPER = tuple(0xD503201F + i for i in range(16))


def fake_archived():
    records = dict(mod.V9_CONTROLLER_OPCODES)
    records.update({src: mod.encode_b(src, dest)
                    for src, dest in mod.BRANCH_TARGETS.items()})
    pos = 0
    for start, count in mod.HELPER_SEGMENTS:
        for i in range(count):
            records[start + 4*i] = FAKE_HELPER[pos]
            pos += 1
    assert len(records) == 22
    return mod.serialize_ips32(records)


def isolated_from_fake(blob):
    records = mod.parse_ips32(blob)
    return mod.serialize_ips32({x: word for x, word in records.items()
                                if x not in mod.V9_CONTROLLER_OPCODES})


class ReproduceTests(unittest.TestCase):
    def test_actual_source_layout_contains_16_helper_words(self):
        self.assertEqual(len(mod.ASM), 16)
        self.assertEqual(sum(count for _, count in mod.HELPER_SEGMENTS), 16)
        self.assertEqual(len(mod.BRANCH_TARGETS), 4)
        self.assertEqual(mod.BRANCH_TARGETS[mod.HOOK], 0x006E1864)

    def test_exact_diff_only_two_controller_sites(self):
        v9 = fake_archived()
        expected = isolated_from_fake(v9)
        with patch.object(mod, "OLD_IPS_SHA256", mod.sha256(v9)), \
             patch.object(mod, "V10_IPS_SHA256", mod.sha256(expected)):
            actual = mod.build_from_v9_ips(v9, FAKE_HELPER)
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 209)
        ips = mod.parse_ips32(actual)
        self.assertEqual(len(ips), 20)
        self.assertNotIn(mod.GUARD, ips)
        self.assertNotIn(mod.PRESENT, ips)

    def test_wrong_helper_is_rejected(self):
        v9 = fake_archived()
        with patch.object(mod, "OLD_IPS_SHA256", mod.sha256(v9)):
            with self.assertRaisesRegex(ValueError, "Helper opcode mismatch"):
                mod.build_from_v9_ips(v9, FAKE_HELPER[:-1]+(0,))

    def test_missing_controller_or_extra_offset_is_rejected(self):
        records = mod.parse_ips32(fake_archived())
        records.pop(mod.GUARD)
        bad = mod.serialize_ips32(records)
        with patch.object(mod, "OLD_IPS_SHA256", mod.sha256(bad)):
            with self.assertRaisesRegex(ValueError, "offset set"):
                mod.build_from_v9_ips(bad, FAKE_HELPER)
        records = mod.parse_ips32(fake_archived())
        records[0x110] = 0
        bad = mod.serialize_ips32(records)
        with patch.object(mod, "OLD_IPS_SHA256", mod.sha256(bad)):
            with self.assertRaisesRegex(ValueError, "offset set"):
                mod.build_from_v9_ips(bad, FAKE_HELPER)

    def test_wrong_branch_detected_even_if_hash_is_patched(self):
        records = mod.parse_ips32(fake_archived())
        records[mod.HOOK] = 0x14000000
        bad = mod.serialize_ips32(records)
        with patch.object(mod, "OLD_IPS_SHA256", mod.sha256(bad)):
            with self.assertRaisesRegex(ValueError, "trampoline branch"):
                mod.build_from_v9_ips(bad, FAKE_HELPER)

    def test_ips32_parser_rejects_short_rle_duplicate_and_trailing(self):
        v9 = fake_archived()
        for malformed in (b"IPS32",
                          b"IPS32EEOFxxx",
                          v9[:-1],
                          b"IPS32" + (0x100).to_bytes(4,"big") + b"\0\0" + b"EEOF"):
            with self.assertRaises(ValueError):
                mod.parse_ips32(malformed)
        rec = {0x108:0xD503201F}
        raw = mod.serialize_ips32(rec)
        duplicate = raw[:-4] + raw[5:-4] + b"EEOF"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            mod.parse_ips32(duplicate)

    def test_end_to_end_private_archive_reproduction(self):
        blob = fake_archived()
        expected = isolated_from_fake(blob)
        with tempfile.TemporaryDirectory() as tmp:
            archived = Path(tmp)/"private-v9.zip"
            with zipfile.ZipFile(archived, "w") as z:
                z.writestr(f"0400486024DEC000/V9/exefs/{mod.BUILD}.ips", blob)
                z.writestr("notes.txt", "Synthetic-only test")
            with patch.object(mod,"OLD_ZIP_SHA256",mod.sha256(archived.read_bytes())), \
                 patch.object(mod,"OLD_IPS_SHA256",mod.sha256(blob)), \
                 patch.object(mod,"V10_IPS_SHA256",mod.sha256(expected)):
                self.assertEqual(mod.reproduce_from_archive(archived, FAKE_HELPER), expected)
            with self.assertRaisesRegex(ValueError, "Wrong archived V9 ZIP"):
                mod.reproduce_from_archive(archived, FAKE_HELPER)

    def test_source_hash_is_required(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            mod.build_from_v9_ips(fake_archived(), FAKE_HELPER)


if __name__ == "__main__":
    unittest.main()
