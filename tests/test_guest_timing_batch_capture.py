"""Synthetic tests for one-session guarded E0F3 timing batch capture."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mods" / "fps" / "research" / "true-dynamic"))
import guest_timing_batch_capture as batch

BASE = 0x81000000
PREFIX = struct.pack("<32I", *([0xD503201F] * 32))


class FakeRSP:
    def __init__(self, incorrect=None, truncated=None):
        self.incorrect = incorrect
        self.truncated = truncated
        self.reads = []

    def mem(self, addr, count):
        self.reads.append((addr, count))
        if addr == BASE + batch.HOOKS[batch.BUILD] and count == 4:
            return struct.pack("<I", 0x1E201828)
        for offset, opcode in batch.ORIGINAL_CONTROLLER_CHECKS.items():
            if addr == BASE + offset and count == 4:
                return struct.pack("<I", opcode if self.incorrect != offset else 0)
        if addr == BASE + batch.CALLBACK and count == 128:
            return PREFIX if self.incorrect != "callback" else bytes(128)
        for name, offset, size in batch.TARGETS:
            if addr == BASE + offset and count == size:
                data = PREFIX + bytes([0x42]) * (size - len(PREFIX))
                return data[:-4] if self.truncated == name else data
        raise AssertionError((hex(addr), count))


class BatchCaptureTests(unittest.TestCase):
    def verified(self):
        return patch.object(batch, "CALLBACK_PREFIX_SHA256", hashlib.sha256(PREFIX).hexdigest())

    def test_branch_targets_match_verified_original_code(self):
        self.assertEqual(batch.bl_target(0x03B4F088, 0x97E4754E), 0x0346C5C0)
        self.assertEqual(batch.bl_target(0x03B4F190, 0x972633D8), 0x004DC0F0)

    def test_captures_all_three_verified_windows(self):
        rsp = FakeRSP()
        with self.verified():
            result = batch.capture(rsp, BASE)
        self.assertEqual(len(result["regions"]), 3)
        self.assertEqual([x["length_bytes"] for x in result["regions"]], [4096, 2560, 2560])
        self.assertTrue(all(x["sha256_window"] for x in result["regions"]))
        self.assertEqual(len([r for r in rsp.reads if r[1] > 128]), 3)

    def test_bad_original_controller_rejected_without_large_reads(self):
        rsp = FakeRSP(incorrect=0x03B4F080)
        with self.verified():
            with self.assertRaisesRegex(ValueError, "original controller opcode"):
                batch.capture(rsp, BASE)
        self.assertFalse(any(count > 128 for _, count in rsp.reads))

    def test_wrong_callback_prefix_rejected_before_any_code_windows(self):
        rsp = FakeRSP(incorrect="callback")
        with self.verified():
            with self.assertRaisesRegex(ValueError, "Callback prefix"):
                batch.capture(rsp, BASE)
        self.assertFalse(any(count > 128 for _, count in rsp.reads))

    def test_truncated_region_rejected(self):
        rsp = FakeRSP(truncated="presentation_setter")
        with self.verified():
            with self.assertRaisesRegex(ValueError, "Missing expected original code"):
                batch.capture(rsp, BASE)

    def test_wrong_build_rejected_before_any_reads(self):
        rsp = FakeRSP()
        with self.assertRaisesRegex(ValueError, "only for original E0F3"):
            batch.capture(rsp, BASE, "33FA")
        self.assertFalse(rsp.reads)

    def test_invalid_base_rejected_without_reads(self):
        rsp = FakeRSP()
        with self.assertRaisesRegex(ValueError, "Invalid current-session"):
            batch.capture(rsp, 3)
        self.assertFalse(rsp.reads)

    def test_non_bl_rejected(self):
        with self.assertRaisesRegex(ValueError, "Expected"):
            batch.bl_target(0x03B4F088, 0xD503201F)


if __name__ == "__main__":
    unittest.main()
