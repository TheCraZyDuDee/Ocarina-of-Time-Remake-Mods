"""Executable-free checks of the static frame-step fingerprint inspector."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "mods" / "fps" / "research" / "true-dynamic" / "inspect_frame_step.py"
spec = importlib.util.spec_from_file_location("inspect_frame_step", MODULE)
inspector = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = inspector
spec.loader.exec_module(inspector)


class FrameStepChecks(unittest.TestCase):
    def test_original_hook_and_rate_select(self):
        self.assertEqual(len(inspector.SITES), 2)
        for build, sites in inspector.SITES.items():
            self.assertEqual(sites["sim_step_divide"][1], 0x1E201828)
            self.assertEqual(sites["base_rate_60_or_30"][1], 0x1E220C21)
            self.assertEqual(sites["target_fps_float_at_state_2c8"][1], 0xBD42CAA0)
            self.assertEqual(sites["manager_pointer_at_context_a8"][1], 0xF9405408)
            self.assertEqual(sites["fps_state_from_manager_20"][1], 0xF9401115)
            self.assertLess(sites["target_fps_float_at_state_2c8"][0], sites["sim_step_divide"][0])
            self.assertEqual(sites["first_instruction_after_hook"][0], sites["sim_step_divide"][0] + 4)

    def test_v9_timer_field_cannot_be_verified_from_static_fingerprints(self):
        self.assertTrue(all("last_frame_ticks" not in name for sites in inspector.SITES.values() for name in sites))

    def test_rejects_unknown_image_and_overrun(self):
        with self.assertRaises(ValueError):
            inspector.original_nso_build_id(b"bad")
        with self.assertRaises(ValueError):
            inspector.u32(bytes(0x100), 0)


if __name__ == "__main__":
    unittest.main()
