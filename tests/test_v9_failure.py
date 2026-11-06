"""Regression checks against the V9 failure hypothesis.

These are mathematical consequences of the algorithm, NOT runtime tests.
"""
import importlib.util
from pathlib import Path
import sys
import unittest

root = (Path(__file__).resolve().parents[1] / "mods" / "fps" /
        "research" / "true-dynamic" / "v9_failure_model.py")
spec = importlib.util.spec_from_file_location("v9_failure_model", root)
model = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = model
spec.loader.exec_module(model)


class V9FailureRegression(unittest.TestCase):
    def test_four_ticks_produces_reported_speed_profile(self):
        self.assertAlmostEqual(model.implied_game_speed(15, 4), 1.0)
        self.assertAlmostEqual(model.implied_game_speed(30, 4), 2.0)
        self.assertAlmostEqual(model.implied_game_speed(60, 4), 4.0)
        self.assertLess(model.implied_game_speed(10, 4), 1.0)

    def test_input_saturates_above_four_frame_threshold(self):
        minimum = model.threshold_ticks()
        self.assertAlmostEqual(minimum, 2_083_333.3333333333)
        self.assertEqual(model.v9_step_from_ticks(minimum * 2), 4)
        self.assertEqual(model.v9_step_from_ticks(model.GUEST_COUNTER_HZ), 4)

    def test_true_delta_would_not_saturate_above_15_fps(self):
        for fps in (15, 20, 30, 45, 60):
            ticks = model.expected_duration_ticks(fps)
            step = model.v9_step_from_ticks(ticks)
            self.assertAlmostEqual(step, 60 / fps)
            self.assertAlmostEqual(model.implied_game_speed(fps, step), 1)

    def test_v9_has_arbitrary_unproven_field(self):
        builder = root.with_name("real_elapsed_probe_builder.py").read_text()
        self.assertIn("ldr x8, [x8, #0x100]", builder)
        self.assertIn("V9 FAILED", builder)
        self.assertIn("--reproduce-known-bad-v9", builder)

    def test_reject_invalid(self):
        with self.assertRaises(ValueError):
            model.v9_step_from_ticks(-1)
        with self.assertRaises(ValueError):
            model.implied_game_speed(-1, 2)


if __name__ == "__main__":
    unittest.main()
