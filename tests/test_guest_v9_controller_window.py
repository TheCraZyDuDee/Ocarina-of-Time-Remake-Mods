"""Synthetic original-E0F3 guard/presentation window tests; no game files."""
from pathlib import Path
import struct
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "mods/fps/research/true-dynamic"
sys.path.insert(0, str(SCRIPTS))
import guest_v9_controller_window as model

BASE = 0x81000000

class FakeRSP:
    def __init__(self, corrupted=None, incomplete=False):
        self.corrupted = corrupted
        self.incomplete = incomplete
        self.reads = []

    def mem(self, addr, size):
        self.reads.append((addr, size))
        if addr == BASE + model.HOOKS[model.BUILD] and size == 4:
            return struct.pack("<I", 0x1E201828)
        for off, word in model.CHECKS.items():
            if addr == BASE + off and size == 4:
                return struct.pack("<I", word if self.corrupted != off else 0)
        if addr == BASE + model.START and size == model.SIZE:
            words = [0xD503201F] * (model.SIZE // 4)
            for off, original in model.CHECKS.items():
                words[(off - model.START) // 4] = original
            blob = struct.pack(f"<{len(words)}I", *words)
            return blob[:-4] if self.incomplete else blob
        raise AssertionError((hex(addr), size))

class TestGuardControllerWindow(unittest.TestCase):
    def test_guard_target_and_original_interval_source(self):
        self.assertEqual(model.decode_tbnz_target(model.GUARD, model.CHECKS[model.GUARD]),
                         0x03B4F074)
        self.assertEqual(model.CHECKS[model.PRESENT], 0xB9404A81)

    def test_original_window_is_bounded_and_hashed(self):
        rsp = FakeRSP()
        result = model.capture(rsp, BASE)
        self.assertEqual(len(result["instruction_words_u32_le"]), 512)
        self.assertEqual(result["guard_original_branch_target"], "main+0x03b4f074")
        self.assertEqual(max(size for _, size in rsp.reads), 2048)

    def test_original_source_fingerprint_guard(self):
        rsp = FakeRSP(corrupted=model.PRESENT)
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            model.capture(rsp, BASE)
        self.assertFalse(any(size == model.SIZE for _, size in rsp.reads))

    def test_bounded_read_short_fails(self):
        with self.assertRaisesRegex(RuntimeError, "Incomplete"):
            model.capture(FakeRSP(incomplete=True), BASE)

    def test_wrong_build_and_bad_base_fail_before_access(self):
        for base, build in ((BASE, "33FA"), (3, model.BUILD)):
            rsp = FakeRSP()
            with self.assertRaises(ValueError):
                model.capture(rsp, base, build)
            self.assertEqual(rsp.reads, [])

    def test_rejects_non_testbit_branch(self):
        with self.assertRaisesRegex(ValueError, "Expected"):
            model.decode_tbnz_target(model.GUARD, 0xD503201F)


if __name__ == "__main__":
    unittest.main()
