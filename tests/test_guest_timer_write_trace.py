"""Synthetic write-watchpoint protocol tests; no game executable or emulator."""
import pathlib
import struct
import sys
import unittest

SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[1] / "mods" / "fps" / "research" / "true-dynamic"
sys.path.insert(0, str(SCRIPT_DIR))
import guest_timer_write_trace as trace

BASE = 0x81000000
HOOK = BASE + trace.HOOKS['E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348']
BUILD = 'E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348'
STATE = 0x10000000


class FakeRsp:
    def __init__(self):
        self.commands = []
        self.running = False
        self.observed = 0
        self.fail_hook = False
        self.unexpected_event = False

    def packet(self, cmd):
        self.commands.append(cmd)
        if cmd.startswith(('Z0,', 'z0,', 'Z2,', 'z2,', 'Hg')):
            return 'OK'
        if cmd == 'c':
            if any(x.startswith('Z2,') for x in self.commands):
                if self.unexpected_event:
                    return 'T05thread:1;'
                self.observed += 1
                return 'T05thread:1;watch:10000100;'
            return 'T05thread:1;'
        if cmd == 's':
            return 'T05thread:1;'
        raise AssertionError(cmd)

    def regs(self):
        # first breakpoint stops at frame-step; watchpoint stops at code writer
        at_watch = any(x.startswith('Z2,') for x in self.commands)
        return {'pc': BASE+0xABCDEF if at_watch else HOOK,
                'x21': STATE}

    def mem(self, addr, length):
        if addr == HOOK:
            return struct.pack('<I', 0 if self.fail_hook else trace.ORIGINAL_HOOK_INSN)
        if addr == STATE+0x100:
            return struct.pack('<Q', 1_000_000+self.observed*50_000)
        raise AssertionError((addr, length))

    def send_continue(self):
        self.running = True


class WatchTests(unittest.TestCase):
    def test_writer_hit_sequence(self):
        rsp = FakeRsp()
        result = trace.trace_writes(rsp, base=BASE, build_id=BUILD, hits=2)
        self.assertTrue(rsp.running)
        self.assertEqual(len(result['observations']), 2)
        self.assertEqual([a['value_relative_to_initial'] for a in result['observations']], [50000,100000])
        self.assertEqual(result['observations'][0]['writer_code_location'],'main+0x00abcdef')
        self.assertEqual(sum(x.startswith('Z0,') for x in rsp.commands),1)
        self.assertEqual(sum(x.startswith('z0,') for x in rsp.commands),1)
        self.assertEqual(sum(x.startswith('Z2,') for x in rsp.commands),2)
        self.assertEqual(sum(x.startswith('z2,') for x in rsp.commands),2)
        self.assertFalse(any(x.startswith(('M','X','P')) for x in rsp.commands))

    def test_mismatch_does_not_arm(self):
        rsp = FakeRsp()
        rsp.fail_hook=True
        with self.assertRaises(ValueError):
            trace.trace_writes(rsp, base=BASE, build_id=BUILD)
        self.assertFalse(any(x.startswith(('Z0','Z2')) for x in rsp.commands))
        self.assertFalse(rsp.running)

    def test_unexpected_debugger_event_cleans_up(self):
        rsp = FakeRsp()
        rsp.unexpected_event = True
        with self.assertRaisesRegex(RuntimeError,'without the expected'):
            trace.trace_writes(rsp, base=BASE, build_id=BUILD)
        self.assertTrue(rsp.running)
        self.assertEqual(sum(x.startswith('z2,') for x in rsp.commands),1)

    def test_bad_offset_rejected_without_debugger_access(self):
        rsp=FakeRsp()
        with self.assertRaises(ValueError):
            trace.trace_writes(rsp,base=BASE,build_id=BUILD,offset=0x208)
        self.assertFalse(rsp.commands)

    def test_outside_main_classification(self):
        self.assertEqual(trace.identify_location(0x90000000,BASE), 'outside_main_module')


if __name__=='__main__':
    unittest.main()
