"""Synthetic tests of bounded read-only E0F3 frame-step follow-up."""
from pathlib import Path
import struct
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / "mods" / "fps" / "research" / "true-dynamic"
sys.path.insert(0, str(PATH))
import guest_frame_step_followup as mod

BASE = 0x81000000


class FakeRSP:
    def __init__(self, altered=None):
        self.altered = altered
        self.reads = []

    def mem(self, address, size):
        self.reads.append((address, size))
        if (address, size) == (BASE + mod.HOOKS[mod.BUILD], 4):
            return struct.pack("<I", 0x1E201828)
        for offset, word in mod.ORIGINAL_CHECKS.items():
            if (address, size) == (BASE + offset, 4):
                if self.altered == offset:
                    word = 0
                return struct.pack("<I", word)
        for _, start, count in mod.WINDOWS:
            if (address, size) == (BASE + start, count):
                return struct.pack("<I", 0xD503201F) * (count // 4)
        raise AssertionError((address, size))


class TestFrameStepFollowup(unittest.TestCase):
    def test_call_target(self):
        self.assertEqual(mod.decode_bl_target(mod.CALL_SITE,
                                              mod.ORIGINAL_CHECKS[mod.CALL_SITE]), mod.CALLEE)
    def test_valid_capture(self):
        rsp = FakeRSP()
        result = mod.capture_followup(rsp, BASE)
        self.assertEqual(len(result["regions"]), 2)
        self.assertEqual([len(r["instruction_words_u32_le"]) for r in result["regions"]],
                         [0x600 // 4, 0x700 // 4])
        self.assertEqual(len(rsp.reads), 1 + len(mod.ORIGINAL_CHECKS) + 2)
    def test_opcode_mismatch_prevents_code_excerpts(self):
        rsp = FakeRSP(altered=mod.CALL_SITE)
        with self.assertRaisesRegex(ValueError, "opcode mismatch"):
            mod.capture_followup(rsp, BASE)
        self.assertFalse(any(n > 4 for _, n in rsp.reads))
    def test_rejects_other_build_without_reads(self):
        rsp = FakeRSP()
        with self.assertRaisesRegex(ValueError, "only for E0F3"):
            mod.capture_followup(rsp, BASE, "33FA")
        self.assertFalse(rsp.reads)
    def test_invalid_base_before_reads(self):
        rsp = FakeRSP()
        with self.assertRaisesRegex(ValueError, "Invalid"):
            mod.capture_followup(rsp, 3)
        self.assertFalse(rsp.reads)
    def test_bl_decoder_rejects_non_branch(self):
        with self.assertRaisesRegex(ValueError, "BL"):
            mod.decode_bl_target(mod.CALL_SITE, 0xD503201F)


if __name__ == "__main__":
    unittest.main()
