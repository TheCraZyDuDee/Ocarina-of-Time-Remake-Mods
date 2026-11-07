#!/usr/bin/env python3
"""Execute the published True Dynamic IPS in a synthetic ARM64 machine.

Optional developer check: pip install unicorn==2.1.4
Run from any directory: python3 tools/audit_dynamic.py -v
This tests the helper, not the game or Eglantine performance.
"""
from pathlib import Path
import hashlib
import math
import random
import struct
import sys
import unittest
import zipfile

try:
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn import arm64_const as arm
except ImportError:
    raise SystemExit("Install the optional audit dependency: pip install unicorn==2.1.4")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mods" / "fps"))
import build


def run_helper(ticks, frequency=31_250_000, nominal=60.0):
    machine = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    machine.mem_map(0x006E0000, 0x20000)
    machine.mem_map(0x01000000, 0x10000)
    machine.mem_map(0x02000000, 0x10000)
    archive = ROOT / "releases" / build.OUTPUT_NAMES["true-dynamic"]
    with zipfile.ZipFile(archive) as z:
        payload = z.read(f"{build.TITLE_ID}/{build.MODES['true-dynamic'][0]}/exefs/{build.E0F3}.ips")
    if hashlib.sha256(payload).hexdigest() != build.EXPECTED_PATCH_SHA256["true-dynamic"][build.E0F3]:
        raise AssertionError("Published IPS hash mismatch")
    for address, word in build.parse_ips32(payload).items():
        machine.mem_write(address, struct.pack("<I", word))

    # Synthetic objects follow the pointer chain read by the actual helper.
    for address, value in ((0x010000A8, 0x01001000),
                           (0x01001020, 0x01002000),
                           (0x01002100, ticks & ((1 << 64) - 1))):
        machine.mem_write(address, struct.pack("<Q", value))
    general = [getattr(arm, f"UC_ARM64_REG_X{i}") for i in range(31)]
    vectors = [getattr(arm, f"UC_ARM64_REG_Q{i}") for i in range(32)]
    for i, reg in enumerate(general):
        machine.reg_write(reg, 0x12340000 + i)
    for i, reg in enumerate(vectors):
        machine.reg_write(reg, (0xFEDCBA9876543210 << 64) | (0x1234567800000000 + i))
    machine.reg_write(arm.UC_ARM64_REG_X19, 0x01000000)
    machine.reg_write(arm.UC_ARM64_REG_S1, struct.unpack("<I", struct.pack("<f", nominal))[0])
    machine.reg_write(arm.UC_ARM64_REG_SP, 0x02008000)
    machine.reg_write(arm.UC_ARM64_REG_NZCV, 0xA0000000)
    machine.reg_write(arm.UC_ARM64_REG_CPACR_EL1, 3 << 20)
    machine.cpr_write(3, 3, 14, 0, 0, frequency)  # CNTFRQ_EL0
    watched = general + vectors + [arm.UC_ARM64_REG_SP, arm.UC_ARM64_REG_NZCV]
    before = {reg: machine.reg_read(reg) for reg in watched}
    instructions, writes = [], []
    machine.hook_add(UC_HOOK_CODE, lambda uc, address, size, data: instructions.append(address))
    machine.hook_add(UC_HOOK_MEM_WRITE, lambda uc, access, address, size, value, data: writes.append((address, size)))
    machine.emu_start(build.DYNAMIC_HOOK, build.DYNAMIC_HOOK + 4, count=64)
    after = {reg: machine.reg_read(reg) for reg in watched}
    result = struct.unpack("<f", struct.pack("<I", machine.reg_read(arm.UC_ARM64_REG_S8)))[0]
    return machine, result, before, after, instructions, writes


class DynamicRuntimeAudit(unittest.TestCase):
    def test_normal_frame_times(self):
        for fps in (15, 20, 30, 45, 60, 90, 120):
            with self.subTest(fps=fps):
                ticks = round(31_250_000 / fps)
                _, result, *_ = run_helper(ticks)
                self.assertAlmostEqual(result, max(0.5, min(4.0, ticks * 60 / 31_250_000)), places=5)

    def test_zero_negative_and_extreme_durations_stay_bounded(self):
        for ticks, expected in ((0, 0.5), (-1, 0.5), (1, 0.5),
                                (31_250_000, 4.0), ((1 << 63) - 1, 4.0),
                                (-(1 << 63), 0.5)):
            with self.subTest(ticks=ticks):
                self.assertEqual(run_helper(ticks)[1], expected)

    def test_counter_frequency_scaling(self):
        for frequency in (19_200_000, 31_250_000, 1_000_000_000):
            with self.subTest(frequency=frequency):
                self.assertAlmostEqual(run_helper(frequency // 30, frequency)[1], 2.0, places=5)

    def test_random_positive_inputs_match_bounded_formula(self):
        rng = random.Random(20261107)
        for _ in range(100):
            ticks = rng.randrange(0, 10_000_000)
            _, result, *_ = run_helper(ticks)
            self.assertTrue(math.isfinite(result))
            self.assertAlmostEqual(result, max(0.5, min(4.0, ticks * 60 / 31_250_000)), places=5)

    def test_register_stack_and_control_flow_contract(self):
        machine, _, before, after, instructions, writes = run_helper(1_041_667)
        self.assertEqual(machine.reg_read(arm.UC_ARM64_REG_PC), build.DYNAMIC_HOOK + 4)
        self.assertEqual(len(instructions), 20)
        self.assertEqual(len(instructions), len(set(instructions)))
        self.assertEqual(writes, [(0x02007FF0, 8), (0x02007FE0, 8)])
        for reg in before:
            if reg not in (arm.UC_ARM64_REG_Q0, arm.UC_ARM64_REG_Q8):
                self.assertEqual(after[reg], before[reg], f"Register {reg} changed")
        # The existing helper saves D0, not Q0. Its upper 64 bits are cleared.
        self.assertEqual(after[arm.UC_ARM64_REG_Q0] & ((1 << 64) - 1),
                         before[arm.UC_ARM64_REG_Q0] & ((1 << 64) - 1))
        self.assertEqual(after[arm.UC_ARM64_REG_Q0] >> 64, 0)


if __name__ == "__main__":
    unittest.main()
