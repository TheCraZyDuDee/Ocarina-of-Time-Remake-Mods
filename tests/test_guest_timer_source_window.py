"""Synthetic tests for the read-only E0F3 timer-source code window."""
from pathlib import Path
import hashlib
import struct
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / "mods" / "fps" / "research" / "true-dynamic"
sys.path.insert(0, str(PATH))
import guest_timer_source_window as mod

BASE = 0x81000000


class Stub:
    def __init__(self, writer=mod.WRITER_OPCODE):
        self.writer = writer
        self.reads = []

    def mem(self, address, size):
        self.reads.append((address, size))
        if (address, size) == (BASE + mod.HOOKS[mod.BUILD], 4):
            return struct.pack('<I', 0x1E201828)
        if (address, size) == (BASE + mod.WRITER_OFFSET, 4):
            return struct.pack('<I', self.writer)
        if (address, size) == (BASE + mod.TIMER_OFFSET, mod.TIMER_SIZE):
            return struct.pack('<I', 0xD503201F) * (size // 4)
        raise AssertionError((address, size))


class TestTimerSourceWindow(unittest.TestCase):
    def test_fixed_bounded_read(self):
        fake = Stub()
        result = mod.capture_timer_source(fake, BASE)
        self.assertEqual(len(result['instruction_words_u32_le']), 96)
        self.assertEqual(result['timer_function_main_offset'], 'main+0x03c41fd0')
        self.assertEqual(result['sha256_window'], hashlib.sha256(
            struct.pack('<I', 0xD503201F) * 96).hexdigest())
        self.assertEqual(fake.reads, [(BASE + mod.HOOKS[mod.BUILD], 4),
                                      (BASE + mod.WRITER_OFFSET, 4),
                                      (BASE + mod.TIMER_OFFSET, 384)])

    def test_wrong_writer_fails_before_dump(self):
        fake = Stub(writer=0)
        with self.assertRaisesRegex(ValueError, 'Writer opcode mismatch'):
            mod.capture_timer_source(fake, BASE)
        self.assertEqual(len(fake.reads), 2)

    def test_other_build_fails_without_reads(self):
        fake = Stub()
        with self.assertRaisesRegex(ValueError, 'only been located'):
            mod.capture_timer_source(fake, BASE, build_id='33FA')
        self.assertEqual(fake.reads, [])

    def test_invalid_base_fails_without_reads(self):
        fake = Stub()
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            mod.capture_timer_source(fake, 3)
        self.assertEqual(fake.reads, [])


if __name__ == '__main__':
    unittest.main()
