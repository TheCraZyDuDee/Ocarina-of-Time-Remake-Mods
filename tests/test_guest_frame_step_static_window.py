"""Synthetic tests for the bounded, read-only E0F3 frame-step inspector."""
from pathlib import Path
import struct
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / "mods" / "fps" / "research" / "true-dynamic"
sys.path.insert(0, str(PATH))
import guest_frame_step_static_window as mod

BASE = 0x81000000


class FakeReadOnlyDebugger:
    def __init__(self, changed=None, hook_word=0x1E201828):
        self.changed = changed
        self.hook_word = hook_word
        self.requests = []

    def mem(self, address, count):
        self.requests.append((address, count))
        if (address, count) == (BASE + mod.HOOK, 4):
            return struct.pack("<I", self.hook_word)
        if (address, count) == (BASE + mod.START, mod.SIZE):
            words = [0xD503201F] * (mod.SIZE // 4)
            for at, op in mod.ORIGINAL_INSTRUCTIONS.items():
                words[(at - mod.START) // 4] = op
            if self.changed is not None:
                words[(self.changed - mod.START) // 4] = 0
            return struct.pack("<256I", *words)
        raise AssertionError((address, count))


class TestFrameStepWindow(unittest.TestCase):
    def test_valid_capture_is_1028_read_only_bytes(self):
        fake = FakeReadOnlyDebugger()
        out = mod.capture_frame_step(fake, BASE)
        self.assertEqual(len(out["instruction_words_u32_le"]), 256)
        self.assertEqual(out["frame_step_divide_word_index"], 0xE4 // 4)
        self.assertEqual(fake.requests, [(BASE + mod.HOOK, 4),
                                         (BASE + mod.START, mod.SIZE)])

    def test_fingerprint_mismatch_fails(self):
        fake = FakeReadOnlyDebugger(changed=0x006E6C98)
        with self.assertRaisesRegex(ValueError, "instruction mismatch"):
            mod.capture_frame_step(fake, BASE)

    def test_wrong_hook_fails_before_window(self):
        fake = FakeReadOnlyDebugger(hook_word=0)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            mod.capture_frame_step(fake, BASE)
        self.assertEqual(fake.requests, [(BASE + mod.HOOK, 4)])

    def test_other_build_is_rejected(self):
        fake = FakeReadOnlyDebugger()
        with self.assertRaisesRegex(ValueError, "only verified"):
            mod.capture_frame_step(fake, BASE, "33FA")
        self.assertEqual(fake.requests, [])

    def test_bad_main_base_is_rejected(self):
        fake = FakeReadOnlyDebugger()
        with self.assertRaisesRegex(ValueError, "Invalid"):
            mod.capture_frame_step(fake, 3)
        self.assertEqual(fake.requests, [])


if __name__ == "__main__":
    unittest.main()
