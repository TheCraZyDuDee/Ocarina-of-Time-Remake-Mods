"""Synthetic tests for the read-only timer writer code-window diagnostic."""
from pathlib import Path
import struct
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / "mods" / "fps" / "research" / "true-dynamic"
sys.path.insert(0, str(PATH))
import guest_writer_static_window as win

BASE = 0x81000000
HOOK = BASE + win.HOOKS[win.BUILD]


class FakeReadOnlyDebugger:
    def __init__(self, opcode=None):
        self.opcode = win.HOOKS and (0x1E201828 if opcode is None else opcode)
        self.requests = []

    def mem(self, addr, count):
        self.requests.append((addr, count))
        if addr == HOOK and count == 4:
            return struct.pack("<I", self.opcode)
        if addr == BASE + win.WRITER_OFFSET - win.BEFORE and count == win.BEFORE + win.AFTER:
            return struct.pack("<I", 0xD503201F) * (count // 4)
        raise AssertionError((addr, count))


class TestCodeWindow(unittest.TestCase):
    def test_normal_capture_only_reads_644_bytes(self):
        stub = FakeReadOnlyDebugger()
        report = win.capture_window(stub, BASE)
        self.assertEqual(len(stub.requests), 2)
        self.assertEqual(stub.requests[0], (HOOK, 4))
        self.assertEqual(len(report["instruction_words_u32_le"]), 160)
        self.assertEqual(report["writer_word_index"], 128)
        self.assertEqual(report["instruction_words_u32_le"][128], "0xd503201f")
        self.assertEqual(report["writer_site_main_offset"], "main+0x0346c7ec")

    def test_mismatch_rejected_before_window_read(self):
        stub = FakeReadOnlyDebugger(0)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            win.capture_window(stub, BASE)
        self.assertEqual(stub.requests, [(HOOK, 4)])

    def test_no_guessed_build(self):
        stub = FakeReadOnlyDebugger()
        with self.assertRaisesRegex(ValueError, "not established"):
            win.capture_window(stub, BASE, build_id="33FA")
        self.assertFalse(stub.requests)

    def test_invalid_base_no_reads(self):
        stub = FakeReadOnlyDebugger()
        with self.assertRaisesRegex(ValueError, "Invalid"):
            win.capture_window(stub, 0x123)
        self.assertFalse(stub.requests)


if __name__ == "__main__":
    unittest.main()
