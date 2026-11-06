"""Source-only tests: isolated candidate must not patch V9 guard/present."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

LIB = Path(__file__).resolve().parents[1] / "mods/fps/research/true-dynamic"
sys.path.insert(0, str(LIB))
import isolated_step_research_builder as candidate


CONF = {"guard": 0x100, "present": 0x104, "delta_hook": 0x200}
CAVE = 0x300
WORDS = tuple(0xD503201F for _ in range(16))


def synthetic_module():
    data = bytearray(0x1000)
    original = {
        CONF["guard"]: candidate.ORIGINAL_GUARD,
        CONF["present"]: candidate.ORIGINAL_PRESENT,
        CONF["delta_hook"] - 4: candidate.DIV_NUMERATOR,
        CONF["delta_hook"]: candidate.ORIGINAL_DIV,
        CONF["delta_hook"] + 4: candidate.DIV_NEXT_BRANCH,
    }
    for offset, word in original.items():
        struct.pack_into("<I", data, 0x100 + offset, word)
    return bytes(data)


def cave_picker(data, hook, length):
    assert hook == CONF["delta_hook"]
    return [(CAVE, length)]


class IsolatedStepBuilderTests(unittest.TestCase):
    def setUp(self):
        self.p = patch.object(candidate, "CONFIG", CONF)
        self.p.start()
        self.addCleanup(self.p.stop)

    def test_only_fdiv_hook_and_code_cave_are_patched(self):
        ips, caves, records = candidate.construct_ips(synthetic_module(), WORDS,
                                                       cave_picker=cave_picker)
        self.assertTrue(ips.startswith(b"IPS32") and ips.endswith(b"EEOF"))
        self.assertEqual(caves, [(CAVE, len(WORDS))])
        self.assertEqual(set(records) - set(range(CAVE, CAVE + 4 * (len(WORDS) + 1))),
                         {CONF["delta_hook"]})
        self.assertEqual(len(records), len(WORDS) + 2)
        self.assertNotIn(CONF["guard"], records)
        self.assertNotIn(CONF["present"], records)
        self.assertEqual(candidate.previous.decode_b(CONF["delta_hook"],
                          records[CONF["delta_hook"]]), CAVE)

    def test_rejects_modified_original_guard(self):
        d = bytearray(synthetic_module())
        struct.pack_into("<I", d, 0x100 + CONF["guard"], 0xD503201F)
        with self.assertRaisesRegex(ValueError, "opcode mismatch"):
            candidate.construct_ips(bytes(d), WORDS, cave_picker=cave_picker)

    def test_rejects_modified_original_presentation(self):
        d = bytearray(synthetic_module())
        struct.pack_into("<I", d, 0x100 + CONF["present"], 0x52800021)
        with self.assertRaisesRegex(ValueError, "opcode mismatch"):
            candidate.construct_ips(bytes(d), WORDS, cave_picker=cave_picker)

    def test_rejects_modified_original_div(self):
        d = bytearray(synthetic_module())
        struct.pack_into("<I", d, 0x100 + CONF["delta_hook"], 0x14000000)
        with self.assertRaisesRegex(ValueError, "opcode mismatch"):
            candidate.construct_ips(bytes(d), WORDS, cave_picker=cave_picker)

    def test_rejects_code_cave_overlap_and_missing_capacity(self):
        with self.assertRaisesRegex(ValueError, "Unexpected original instruction"):
            candidate.construct_ips(synthetic_module(), WORDS,
                                    cave_picker=lambda data, hook, length: [(CONF["guard"], length)])
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            candidate.construct_ips(synthetic_module(), WORDS,
                                    cave_picker=lambda data, hook, length: [(CAVE, 2)])

    def test_rejects_invalid_helper_length(self):
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            candidate.construct_ips(synthetic_module(), (), cave_picker=cave_picker)
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            candidate.construct_ips(synthetic_module(), (0,) * 129, cave_picker=cave_picker)

    def test_output_is_private_opt_in_zip_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "research.zip"
            with patch.object(candidate, "load_verified_inspection_image", return_value=synthetic_module()), \
                 patch.object(candidate, "validate_inspection_image", return_value=[]), \
                 patch.object(candidate.previous, "assemble", return_value=WORDS), \
                 patch.object(candidate.previous, "find_caves", side_effect=cave_picker):
                result = candidate.generate_zip(Path(t) / "private.nso", out)
                self.assertEqual(result["ips_instruction_records"], len(WORDS) + 2)
                self.assertTrue(out.exists())
                with zipfile.ZipFile(out) as z:
                    self.assertEqual(z.testzip(), None)
                    self.assertEqual(len(z.namelist()), 2)
                    self.assertTrue(any("UNVALIDATED" in s for s in z.namelist()))
                with self.assertRaisesRegex(ValueError, "overwrite"):
                    candidate.generate_zip(Path(t) / "private.nso", out)


if __name__ == "__main__":
    unittest.main()
