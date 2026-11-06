"""Synthetic protocol tests for active timing-config call-site trace (E0F3)."""
from pathlib import Path
import struct
import sys
import unittest

LIB = Path(__file__).resolve().parents[1] / "mods" / "fps" / "research" / "true-dynamic"
sys.path.insert(0, str(LIB))
import guest_frame_step_path_trace as mod

BASE = 0x81000000
FRAME = 0x90000000
MANAGER = 0x90100000
FPS = 0x90200000


class FakeRSP:
    def __init__(self, sites=None, *, mismatch=None):
        self.sites = list(sites or [BASE + 0x006E6DD8])
        self.mismatch = mismatch
        self.events = []
        self.records = []
        self.n = 0
        self.reads = []

    def mem(self, addr, size):
        self.reads.append((addr, size))
        if (addr, size) == (BASE + mod.HOOKS[mod.BUILD], 4):
            return struct.pack("<I", 0x1E201828)
        for site, expected in mod.SITES.items():
            if (addr, size) == (BASE + site, 4):
                return struct.pack("<I", 0 if self.mismatch == site else expected)
        if (addr, size) == (FRAME + 0xA8, 8):
            return struct.pack("<Q", MANAGER)
        if (addr, size) == (MANAGER + 0x20, 8):
            return struct.pack("<Q", FPS)
        if (addr, size) == (FRAME + 0xD38, 4):
            return struct.pack("<I", 43)
        if (addr, size) == (FRAME + 0xD50, 4):
            return struct.pack("<I", 3000 + self.n)
        if (addr, size) == (FPS + 0x2C8, 4):
            return struct.pack("<I", 60)
        raise AssertionError((hex(addr), size))

    def packet(self, request):
        self.events.append(request)
        if request.startswith(("Z0,", "z0,", "Hg")):
            return "OK"
        if request in ("c", "s"):
            if request == "s":
                self.n += 1
            return "T05thread:01;"
        raise AssertionError(request)

    def regs(self):
        return {"pc": self.sites[min(self.n, len(self.sites) - 1)],
                "x19": FRAME, "x21": 0xD0000000, "s0": 1.0, "s8": 1.0}

    def send_continue(self):
        self.events.append("final_continue")


class TestPathTrace(unittest.TestCase):
    def test_original_branch_targets(self):
        for site, opcode in mod.SITES.items():
            self.assertEqual(mod.branch_target(site, opcode), mod.TARGET)

    def test_valid_two_sites_traced_and_cleaned(self):
        rsp = FakeRSP([BASE + 0x006E6DD8, BASE + 0x006E70F8])
        result = mod.trace_paths(rsp, BASE, 2)
        self.assertEqual(result["total_hits"], 2)
        self.assertEqual(len(result["hits_by_call_site"]), 2)
        self.assertEqual([x["integer_target_fps_2c8"] for x in result["hits"]], [60, 60])
        self.assertEqual([x["incoming_s0"] for x in result["hits"]], [1.0, 1.0])
        self.assertEqual(rsp.events[-1], "final_continue")
        self.assertTrue(any(x.startswith("z0,") for x in rsp.events))
        # Code-site X21 is deliberately incorrect; only context chain was trusted.
        self.assertFalse(any(a == 0xD00002C8 for a, n in rsp.reads))

    def test_fails_closed_on_bad_call_site(self):
        rsp = FakeRSP(mismatch=0x006E6DD8)
        with self.assertRaisesRegex(ValueError, "Original BL mismatch"):
            mod.trace_paths(rsp, BASE, 3)
        self.assertFalse(any(x.startswith("Z0,") for x in rsp.events))
        self.assertEqual(rsp.events[-1], "final_continue")

    def test_rejects_unexpected_hook_site(self):
        rsp = FakeRSP()
        with self.assertRaisesRegex(ValueError, "Invalid current"):
            mod.trace_paths(rsp, 3, 1)
        self.assertFalse(rsp.reads)

    def test_bad_count_does_not_attach(self):
        rsp = FakeRSP()
        with self.assertRaisesRegex(ValueError, "Hit count"):
            mod.trace_paths(rsp, BASE, 20)
        self.assertFalse(rsp.reads)
        self.assertFalse(rsp.events)

    def test_rejects_non_branch(self):
        with self.assertRaisesRegex(ValueError, "Not an original"):
            mod.branch_target(0x006E6DD8, 0xD503201F)


if __name__ == "__main__":
    unittest.main()
