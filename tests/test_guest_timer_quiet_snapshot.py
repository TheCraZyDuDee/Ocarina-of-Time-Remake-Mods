"""Executable-free synthetic tests for sparse timing snapshot safeguards."""
from pathlib import Path
import struct
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / "mods" / "fps" / "research" / "true-dynamic"
sys.path.insert(0, str(PATH))
import guest_timer_quiet_snapshot as mod

BASE, STATE, ID = 0x81000000, 0x90004000, 0x80001000

class Sock:
    def __init__(self): self.sent=[]
    def sendall(self, data): self.sent.append(data)

class Debugger:
    def __init__(self, *, changed=False, bad_stop=False):
        self.changed,self.bad_stop=changed,bad_stop
        self.sock=Sock();self.commands=[];self.continues=0;self.calls=[]
    def read_hook(self, addr): self.calls.append(('hook',addr))
    def packet(self, command):
        self.commands.append(command)
        if command.startswith(('Z0,','z0,','Hg')):return 'OK'
        if command in ('c','s'):return 'T05thread:01;'
        raise AssertionError(command)
    def regs(self):return {'pc':BASE + mod.HOOKS[mod.BUILD],'x21':STATE}
    def mem(self, address, size):
        self.calls.append(('mem',address,size))
        if (address,size)==(STATE,8):
            ident=ID + (8 if self.changed else 0)
            return struct.pack('<Q',ident)
        if (address,size)==(STATE+0x100,mod.WINDOW_SIZE):
            out=bytearray(mod.WINDOW_SIZE)
            for off,n in [(0,625000),(8,100000),(0x48,450000),(0x50,600000)]:
                struct.pack_into('<Q',out,off,n)
            return bytes(out)
        raise AssertionError((address,size))
    def send_continue(self):self.continues+=1
    def recv_packet(self):return 'E01' if self.bad_stop else 'T05thread:01;'

class TestQuietSnapshot(unittest.TestCase):
    def test_locates_unhooks_and_steps(self):
        rsp=Debugger()
        self.assertEqual(mod.locate_state(rsp,BASE),(STATE,ID))
        self.assertEqual(rsp.commands,[f'Z0,{BASE+mod.HOOKS[mod.BUILD]:x},4', 'c',
                                       'Hg01', f'z0,{BASE+mod.HOOKS[mod.BUILD]:x},4','s'])
    def test_snapshot_decode(self):
        rsp=Debugger()
        snapshot=mod.snapshot_state(rsp,STATE,ID)
        self.assertEqual(snapshot['elapsed_100_ms_if_guest_counter_ticks'],20.0)
        self.assertFalse(snapshot['would_saturate_v9_at_60hz'])
        self.assertEqual(snapshot['partial_148_u64'],450000)
    def test_free_run_and_always_resume(self):
        rsp=Debugger()
        samples=mod.collect_snapshots(rsp,STATE,ID,3,2,sleep=lambda secs: None)
        self.assertEqual(len(samples),3)
        self.assertEqual(rsp.continues,4)
        self.assertEqual(rsp.sock.sent,[b'\x03']*3)
    def test_changed_identity_aborts_and_resumes(self):
        rsp=Debugger(changed=True)
        with self.assertRaisesRegex(RuntimeError,'identity changed'):
            mod.collect_snapshots(rsp,STATE,ID,2,2,sleep=lambda secs: None)
        self.assertEqual(rsp.continues,2)
    def test_bad_stop_aborts_and_resumes(self):
        rsp=Debugger(bad_stop=True)
        with self.assertRaisesRegex(RuntimeError,'Unexpected GDB reply'):
            mod.collect_snapshots(rsp,STATE,ID,2,2,sleep=lambda secs: None)
        self.assertEqual(rsp.continues,2)

if __name__=='__main__': unittest.main()
