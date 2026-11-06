"""Offline time-manager structure tests without game files."""
import importlib.util
from pathlib import Path
import sys
import unittest

root=Path(__file__).resolve().parents[1]/"mods"/"fps"/"research"/"true-dynamic"
def load(name):
    spec=importlib.util.spec_from_file_location(name,root/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module

mapper=load("map_time_managers")
rates=load("frame_rate_acceptance")

class TwoControllerResearch(unittest.TestCase):
    def test_shared_setter_both_builds(self):
        self.assertEqual(len(mapper.SITES),2)
        for build in mapper.SITES:
            points=mapper.SITES[build]
            routes=mapper.EDGES[build]
            self.assertNotEqual(points["fps_controller"][0],points["interval_controller"][0])
            self.assertEqual(routes["fps_controller_to_setter"][1],
                             routes["interval_controller_to_setter"][1])
            self.assertEqual(routes["fps_controller_to_setter"][1],
                             points["shared_fps_setter"][0])
            self.assertEqual(points["special_40fps_guard"][1],0x7100A2BF)

    def test_bl_branch_target(self):
        for origin,op,target in [
            (0x4DBDF8,0x940000BE,0x4DC0F0),
            (0x3B4F190,0x972633D8,0x4DC0F0),
            (0x3B4F088,0x97E4754E,0x346C5C0),
            (0x3AF1B20,0x9725B090,0x45DD60),
        ]:
            self.assertEqual(mapper.decode_bl(origin,op),target)
        with self.assertRaises(ValueError):
            mapper.decode_bl(0,0x14000000)
        with self.assertRaises(ValueError):
            mapper.decode_bl(2,0x94000000)

    def test_rate_rejection_examples(self):
        for fps,fallback in [(59,30),(45,30),(40,30),(37,30),(25,20),(17,15),(14,12)]:
            d=rates.decide(fps)
            self.assertFalse(d.accepted_by_initial_guard)
            self.assertEqual(d.suggested_lower_fps,fallback)
        for fps in [60,30,20,15,12,10,6,5,4,3,2,1]:
            self.assertTrue(rates.decide(fps).accepted_by_initial_guard)

    def test_special_guard_requires_both_bits(self):
        self.assertTrue(rates.decide(45,True,True).accepted_by_initial_guard)
        self.assertFalse(rates.decide(45,True,False).accepted_by_initial_guard)
        self.assertFalse(rates.decide(45,False,True).accepted_by_initial_guard)
        self.assertFalse(rates.decide(37,True,True).accepted_by_initial_guard)

    def test_invalid_input(self):
        with self.assertRaises(ValueError): mapper.verify_original(b"bad")
        with self.assertRaises(TypeError): rates.decide(45.0)

if __name__=="__main__":
    unittest.main()
