"""Source-only V9 fractional rate model regression tests."""
from pathlib import Path
import importlib.util
import math
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / "mods" / "fps" / "research" / "true-dynamic" / "v9_rate_coupling_model.py"
spec = importlib.util.spec_from_file_location("v9_rate_coupling_model", PATH)
model = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = model
spec.loader.exec_module(model)


class V9RateCouplingModel(unittest.TestCase):
    def test_nominal_fixed_positive_steps(self):
        self.assertEqual([model.nominal_rate_from_step(s) for s in (1, 1.5, 2, 3, 4)],
                         [60, 40, 30, 20, 15])

    def test_nominal_30fps_and_50fps_math(self):
        clock = model.COUNTER_HZ
        ticks_30 = round(clock / 30)
        ticks_50 = round(clock / 50)
        self.assertEqual(model.nominal_rate_from_step(model.v9_step_from_ticks(ticks_30)), 30)
        self.assertEqual(model.nominal_rate_from_step(model.v9_step_from_ticks(ticks_50)), 50)
        self.assertTrue(model.diagnostic_for_ticks(ticks_30)["accepted_by_general_divisor_rule"])
        self.assertFalse(model.diagnostic_for_ticks(ticks_50)["accepted_by_general_divisor_rule"])

    def test_no_absolute_timestamp_and_clamp(self):
        self.assertEqual(model.v9_step_from_ticks(0), 0.5)
        self.assertEqual(model.v9_step_from_ticks(10 * model.COUNTER_HZ), 4.0)

    def test_captured_30fps_bounds_do_not_reach_cap(self):
        for ticks in (983403, 1021149, 1093400, 1027570, 1101034):
            self.assertLess(model.v9_step_from_ticks(ticks), 4.0)
        rates = [model.diagnostic_for_ticks(t)["hypothetical_nominal_rate"] for t in
                 (983403, 1021149, 1093400, 1027570, 1101034)]
        self.assertEqual(rates, [32, 31, 29, 30, 28])

    def test_input_rejections(self):
        for ticks in (-1, 1 << 63, 0.5):
            with self.assertRaises(ValueError):
                model.v9_step_from_ticks(ticks)
        with self.assertRaises(ValueError):
            model.nominal_rate_from_step(float("nan"))
        with self.assertRaises(ValueError):
            model.v9_step_from_ticks(100, frequency=0)
        with self.assertRaises(ValueError):
            model.v9_step_from_ticks(100, base=0)

    def test_divisor_rule_is_not_a_callback_claim(self):
        self.assertEqual(sorted(model.GENERAL_FPS_DIVISORS),
                         [1,2,3,4,5,6,10,12,15,20,30,60])
        self.assertFalse(model.diagnostic_for_ticks(1_000_000)["accepted_by_general_divisor_rule"])
        self.assertIn("Math only", model.diagnostic_for_ticks(1_000_000)["disclaimer"])


if __name__ == "__main__":
    unittest.main()
