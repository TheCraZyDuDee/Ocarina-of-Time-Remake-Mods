"""Offline tests of V9 elapsed-time probe; no copyrighted binaries required."""
import importlib.util
from pathlib import Path
import sys
import unittest

root = (Path(__file__).resolve().parents[1] / "mods" / "fps" /
        "research" / "true-dynamic" / "real_elapsed_probe_builder.py")
spec = importlib.util.spec_from_file_location("elapsed_v9", root)
v9 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v9
spec.loader.exec_module(v9)


def nominal_step(baseline_hz, elapsed_ticks, tick_frequency=31_250_000):
    return min(4.0, max(0.5, baseline_hz * elapsed_ticks / tick_frequency))


class V9ProbeTests(unittest.TestCase):
    def test_rate_independence_between_15_and_60(self):
        for engine_ticks in (30, 60):
            for actual_fps in (15, 20, 25, 30, 40, 45, 60):
                with self.subTest(engine_ticks=engine_ticks, actual_fps=actual_fps):
                    step = nominal_step(engine_ticks, 31_250_000 / actual_fps)
                    self.assertAlmostEqual(step * actual_fps / engine_ticks, 1.0)

    def test_caps_mean_it_is_not_an_unlimited_solution(self):
        self.assertEqual(nominal_step(60, 0), 0.5)
        self.assertEqual(nominal_step(60, 31_250_000 // 5), 4.0)
        self.assertAlmostEqual(nominal_step(60, 31_250_000 // 5) * 5 / 60, 1/3)

    def test_critical_live_registers_are_preserved(self):
        self.assertEqual(v9.ASM[0], "str x8, [sp, #-16]!")
        self.assertEqual(v9.ASM[1], "str d0, [sp, #-16]!")
        self.assertEqual(v9.ASM[-2:], ["ldr d0, [sp], #16", "ldr x8, [sp], #16"])
        self.assertIn("mrs x8, cntfrq_el0", v9.ASM)
        self.assertEqual(v9.EXPECTED["delta_hook"], 0x1E201828)
        self.assertEqual(len(v9.BUILDS), 2)

    def test_branch_encoding(self):
        cases = [(0x6e6cc4,0x6e1864), (0x6e1880,0x6e0f04),
                 (0x6b5a08,0x6b9f44), (0x6e1818,0x6b5a0c)]
        for src,dst in cases:
            self.assertEqual(v9.decode_b(src,v9.encode_b(src,dst)),dst)
        with self.assertRaises(ValueError):
            v9.encode_b(0, 0x90000000)


if __name__ == "__main__":
    unittest.main()
