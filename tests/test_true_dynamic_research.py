"""Research-only tests; no Nintendo game files and no IPS generation."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "mods" / "fps" / "research" / "true-dynamic"
spec = importlib.util.spec_from_file_location("timing_model", DIRECTORY / "timing_model.py")
timing = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = timing
spec.loader.exec_module(timing)


class TimingResearchTests(unittest.TestCase):
    def test_probes_and_v8a_speed_mismatch(self):
        self.assertEqual(timing.naive_speed_ratio(15, 6), 1.5)
        self.assertEqual(timing.naive_speed_ratio(15, 12), 3)
        self.assertEqual(timing.naive_speed_ratio(30, 2), 1)
        self.assertEqual(timing.naive_speed_ratio(60, 2), 2)

    def test_fixed_step_at_standard_rates(self):
        for fps in (60, 30, 20, 15, 10, 5):
            with self.subTest(fps=fps):
                clock = timing.FixedStepClock(max_updates_per_frame=12)
                plans = timing.emulate_fps(clock, fps, fps)
                self.assertEqual(clock.total_updates, 60)
                self.assertTrue(all(p.caught_up for p in plans))

    def test_fractional_carry(self):
        clock = timing.FixedStepClock()
        plans = timing.emulate_fps(clock, 45, 450)
        self.assertEqual(clock.total_updates, 600)
        self.assertGreater(len({p.fixed_updates for p in plans}), 1)

    def test_rate_transitions(self):
        clock = timing.FixedStepClock()
        for fps in (60, 45, 30, 20, 15):
            timing.emulate_fps(clock, fps, fps)
        self.assertEqual(clock.total_updates, 5 * 60)

    def test_low_rate_budget_does_not_guarantee_correct_speed(self):
        clock = timing.FixedStepClock(max_updates_per_frame=12)
        plan = timing.emulate_fps(clock, 3, 1)[0]
        self.assertEqual(plan.fixed_updates, 12)
        self.assertGreater(plan.pending_whole_updates, 0)
        self.assertFalse(plan.caught_up)
        clock.reset_after_loading()
        self.assertEqual(clock.advance(0).pending_whole_updates, 0)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            timing.FixedStepClock().advance(-1)
        with self.assertRaises(ValueError):
            timing.naive_speed_ratio(-1, 2)


if __name__ == "__main__":
    unittest.main()
