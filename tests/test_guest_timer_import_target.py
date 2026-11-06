"""Synthetic safeguards for the read-only E0F3 resolved-import capture."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / 'mods' / 'fps' / 'research' / 'true-dynamic'
sys.path.insert(0, str(PATH))
import guest_timer_import_target as mod

BASE = 0x81000000
TARGET = 0x90004000
WORDS = (0xD00083F0, 0xF940DA11, 0x9106C210, 0xD61F0220)


class Stub:
    def __init__(self, *, writer=mod.WRITER_WORD, words=WORDS, pointer=TARGET,
                 target_readable=True):
        self.writer, self.words, self.pointer = writer, words, pointer
        self.target_readable = target_readable
        self.reads = []

    def mem(self, addr, size):
        self.reads.append((addr, size))
        if (addr, size) == (BASE + mod.HOOKS[mod.BUILD], 4):
            return struct.pack('<I', 0x1E201828)
        if (addr, size) == (BASE + mod.WRITER_MAIN_OFFSET, 4):
            return struct.pack('<I', self.writer)
        if (addr, size) == (BASE + mod.STUB_MAIN_OFFSET, 16):
            return struct.pack('<4I', *self.words)
        if (addr, size) == (BASE + mod.EXPECTED_GOT_MAIN_OFFSET, 8):
            return struct.pack('<Q', self.pointer)
        if (addr, size) == (self.pointer, mod.TARGET_CAPTURE_BYTES):
            if not self.target_readable:
                raise ValueError('Unmapped')
            return struct.pack('<I', 0xD503201F) * (size // 4)
        raise AssertionError((addr, size))


class TestImportTarget(unittest.TestCase):
    def test_plt_slot(self):
        self.assertEqual(mod.decode_plt_import_slot(WORDS, BASE + mod.STUB_MAIN_OFFSET),
                         BASE + mod.EXPECTED_GOT_MAIN_OFFSET)

    def test_read_only_capture(self):
        stub = Stub()
        data = mod.capture_import_target(stub, BASE)
        self.assertEqual(data['target_code_status'], 'captured')
        self.assertEqual(len(data['instruction_words_u32_le']), 64)
        self.assertEqual(data['sha256_window'], hashlib.sha256(
            struct.pack('<I', 0xD503201F) * 64).hexdigest())
        self.assertEqual(stub.reads[-1], (TARGET, 256))

    def test_writer_mismatch_before_import(self):
        stub = Stub(writer=0)
        with self.assertRaisesRegex(ValueError, 'writer opcode mismatch'):
            mod.capture_import_target(stub, BASE)
        self.assertEqual(len(stub.reads), 2)

    def test_stub_mismatch_before_pointer(self):
        stub = Stub(words=(0, 0, 0, 0))
        with self.assertRaisesRegex(ValueError, 'trampoline opcode shape'):
            mod.capture_import_target(stub, BASE)
        self.assertEqual(len(stub.reads), 3)

    def test_invalid_pointer_never_read_as_code(self):
        stub = Stub(pointer=3)
        data = mod.capture_import_target(stub, BASE)
        self.assertEqual(data['target_code_status'], 'not_read_invalid_or_unresolved_pointer')
        self.assertEqual(len(stub.reads), 4)

    def test_unmapped_target_graceful(self):
        stub = Stub(target_readable=False)
        data = mod.capture_import_target(stub, BASE)
        self.assertEqual(data['target_code_status'], 'not_readable')
        self.assertEqual(data['read_error_type'], 'ValueError')

    def test_other_module_pointer(self):
        stub = Stub()
        data = mod.capture_import_target(stub, BASE)
        self.assertEqual(data['resolved_target_location'], 'outside_main_module')


if __name__ == '__main__':
    unittest.main()
