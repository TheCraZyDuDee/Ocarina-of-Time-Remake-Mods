"""Executable-free tests of sparse E0F3 frame-step state diagnostics."""
import struct
import sys
from pathlib import Path
import unittest

DIRECTORY = Path(__file__).resolve().parents[1] / "mods" / "fps" / "research" / "true-dynamic"
sys.path.insert(0, str(DIRECTORY))
import guest_frame_step_cadence_probe as mod

BASE, FRAME, FPS, CONFIG = 0x81000000, 0x91000000, 0x92000000, 0x93000000
MANAGER, HOLDER = 0x94000000, 0x95000000


class Socket:
    def __init__(self):
        self.events = []

    def sendall(self, data):
        self.events.append(data)


class Debugger:
    def __init__(self, *, bad_slot=False, bad_stop=False):
        self.calls = []
        self.commands = []
        self.continues = 0
        self.sock = Socket()
        self.bad_slot = bad_slot
        self.bad_stop = bad_stop
        self.snapshot = 0

    def mem(self, addr, size):
        self.calls.append((addr, size))
        if (addr, size) == (BASE + mod.HOOKS[mod.BUILD], 4):
            return struct.pack("<I", 0x1E201828)
        if (addr, size) == (FRAME + 0xA8, 8):
            return struct.pack("<Q", MANAGER)
        if (addr, size) == (MANAGER + 0x20, 8):
            return struct.pack("<Q", FPS)
        if (addr, size) == (BASE + mod.RATE_GLOBAL_SLOT_OFFSET, 8):
            return struct.pack("<Q", HOLDER)
        if (addr, size) == (HOLDER, 8):
            return struct.pack("<Q", HOLDER if self.bad_slot else CONFIG)
        if (addr, size) == (FRAME + 0xD38, 4):
            return struct.pack("<I", 3)
        if (addr, size) == (FRAME + 0xD50, 4):
            return struct.pack("<I", 1)
        if (addr, size) == (FRAME + 0xD58, 8):
            return struct.pack("<d", 20.0 + self.snapshot * 100.0)
        if (addr, size) == (FPS + 0x100, 16):
            return struct.pack("<QQ", 1000000, 31250000 * (10 + 4 * self.snapshot))
        if (addr, size) == (FPS + 0x2C8, 4):
            return struct.pack("<I", 60)
        if (addr, size) == (CONFIG + 0x10, 16):
            return struct.pack("<fffI", 1.0, 1.0, 0.01666667, 60)
        raise AssertionError((addr, size))

    def packet(self, cmd):
        self.commands.append(cmd)
        if cmd.startswith(("Z0,", "z0,", "Hg")):
            return "OK"
        if cmd in ("c", "s"):
            return "T05thread:01;"
        raise AssertionError(cmd)

    def regs(self):
        return {
            "pc": BASE + mod.HOOKS[mod.BUILD],
            "x19": FRAME, "x20": CONFIG, "x21": FPS
        }

    def send_continue(self):
        self.continues += 1

    def recv_packet(self):
        return "E01" if self.bad_stop else "T05thread:01;"


class CadenceProbeTest(unittest.TestCase):
    def test_hook_and_pointers_are_verified(self):
        rsp = Debugger()
        self.assertEqual(mod.locate_state(rsp, BASE), (FRAME, FPS, CONFIG))
        self.assertEqual(rsp.commands, [
            f"Z0,{BASE + mod.HOOKS[mod.BUILD]:x},4", "c", "Hg01",
            f"z0,{BASE + mod.HOOKS[mod.BUILD]:x},4", "s"
        ])

    def test_read_numeric_only(self):
        rsp = Debugger()
        val = mod.sample_fields(rsp, BASE, FRAME, FPS, CONFIG)
        self.assertEqual(val["integer_target_fps_2c8"], 60)
        self.assertEqual(val["rate_step_10"]["value"], 1)
        self.assertEqual(val["rate_reciprocal_14"]["value"], 1)
        self.assertEqual(val["rate_nominal_1c_u32"], 60)
        self.assertEqual(val["accum_d58_f64"], 20.0)
        self.assertNotIn("instruction_words_u32_le", val)

    def test_sparse_rates_and_resume(self):
        rsp = Debugger()

        def progress(seconds):
            rsp.snapshot += 1

        vals = mod.run_sparse(rsp, BASE, FRAME, FPS, CONFIG, 2, 4, sleep=progress)
        self.assertEqual(len(vals), 3)
        self.assertEqual(rsp.continues, 3)
        self.assertEqual(rsp.sock.events, [b"\x03", b"\x03"])
        self.assertEqual(vals[1]["change_since_prior"]["accumulator_units_per_guest_second_if_no_reset"], 25)
        self.assertEqual(vals[2]["change_since_prior"]["guest_counter_elapsed_seconds"], 4)

    def test_stale_rate_pointer_fails_closed(self):
        rsp = Debugger(bad_slot=True)
        with self.assertRaisesRegex(RuntimeError, "Rate-configuration global"):
            mod.locate_state(rsp, BASE)
        self.assertIn(f"z0,{BASE + mod.HOOKS[mod.BUILD]:x},4", rsp.commands)

    def test_sparse_interrupt_failure_resumes(self):
        rsp = Debugger(bad_stop=True)
        with self.assertRaisesRegex(RuntimeError, "Unexpected debugger"):
            mod.run_sparse(rsp, BASE, FRAME, FPS, CONFIG, 2, 4, sleep=lambda s: None)
        self.assertEqual(rsp.continues, 2)

    def test_bogus_sample_count_fails_without_reads(self):
        rsp = Debugger()
        with self.assertRaisesRegex(ValueError, "Samples"):
            mod.run_sparse(rsp, BASE, FRAME, FPS, CONFIG, 14, 4, sleep=lambda s: None)
        self.assertFalse(rsp.calls)
        self.assertEqual(rsp.continues, 0)


if __name__ == "__main__":
    unittest.main()
