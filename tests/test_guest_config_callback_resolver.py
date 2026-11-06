"""Executable-free bounded read-only callback resolver tests."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / "mods" / "fps" / "research" / "true-dynamic"
sys.path.insert(0, str(ROOT))
import guest_config_callback_resolver as mod

BASE = 0x81000000
HOLDER = 0x88000000
CONFIG = 0x88100000
CALLBACK = 0x88200000
VTABLE = 0x88300000


class RSP:
    def __init__(self, callback=CALLBACK, method=None, wrong_site=None):
        self.callback = callback
        self.method = method if method is not None else BASE + 0x100000
        self.wrong_site = wrong_site
        self.reads = []

    def mem(self, addr, count):
        self.reads.append((addr, count))
        if (addr, count) == (BASE + mod.HOOKS[mod.BUILD], 4):
            return struct.pack("<I", 0x1E201828)
        for offset, original in mod.CALLEE_CHECKS.items():
            if (addr, count) == (BASE + offset, 4):
                return struct.pack("<I", original if offset != self.wrong_site else 0)
        locations = {
            (BASE + mod.GLOBAL_HOLDER_SLOT, 8): ("Q", HOLDER),
            (HOLDER, 8): ("Q", CONFIG),
            (CONFIG + 0x10, 4): ("f", 1.0),
            (CONFIG + 0x1C, 4): ("I", 60),
            (CONFIG + mod.CONFIG_CALLBACK_FIELD, 8): ("Q", self.callback),
            (CALLBACK, 8): ("Q", VTABLE),
            (VTABLE + mod.VTABLE_METHOD_OFFSET, 8): ("Q", self.method),
        }
        if (addr, count) in locations:
            fmt, val = locations[(addr, count)]
            return struct.pack("<" + fmt, val)
        if (addr, count) == (self.method, mod.CODE_SIZE):
            return struct.pack("<32I", *([0xD503201F] * 32))
        raise AssertionError((hex(addr), count))


class CallbackResolverTests(unittest.TestCase):
    def test_null_callback_no_code_dump(self):
        rsp = RSP(callback=0)
        result = mod.resolve_callback(rsp, BASE)
        self.assertFalse(result["callback_object_present"])
        self.assertNotIn("instruction_words_u32_le", result)
        self.assertEqual(result["config_step"], 1.0)

    def test_in_main_reads_at_most_128_code_bytes(self):
        rsp = RSP()
        result = mod.resolve_callback(rsp, BASE)
        self.assertEqual(result["callback_method_location"], "main+0x00100000")
        self.assertEqual(len(result["instruction_words_u32_le"]), 32)
        self.assertEqual([n for _, n in rsp.reads if n > 8], [mod.CODE_SIZE])

    def test_external_module_fails_closed_without_code_read(self):
        rsp = RSP(method=0x2000000000)
        result = mod.resolve_callback(rsp, BASE)
        self.assertEqual(result["callback_method_location"], "outside_verified_main_text")
        self.assertNotIn("instruction_words_u32_le", result)
        self.assertFalse(any(n == mod.CODE_SIZE for _, n in rsp.reads))

    def test_fingerprint_mismatch_before_pointer_following(self):
        rsp = RSP(wrong_site=0x03B4E36C)
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            mod.resolve_callback(rsp, BASE)
        self.assertFalse(any(n == 8 for _, n in rsp.reads))

    def test_wrong_build_rejected_before_reads(self):
        rsp = RSP()
        with self.assertRaisesRegex(ValueError, "only for E0F3"):
            mod.resolve_callback(rsp, BASE, "33FA")
        self.assertFalse(rsp.reads)

    def test_invalid_callback_pointer_refused(self):
        rsp = RSP(callback=3)
        with self.assertRaisesRegex(RuntimeError, "Callback object pointer invalid"):
            mod.resolve_callback(rsp, BASE)


if __name__ == "__main__":
    unittest.main()
