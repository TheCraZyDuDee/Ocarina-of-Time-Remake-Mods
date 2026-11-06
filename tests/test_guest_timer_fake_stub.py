"""Synthetic end-to-end test using a fake local GDB stub, no game files."""
import pathlib
import socket
import struct
import subprocess
import sys
import threading
import unittest

SCRIPT = (pathlib.Path(__file__).resolve().parents[1] / "mods" / "fps" /
          "research" / "true-dynamic" / "guest_timer_probe.py")
HOOK = 0x80D3A000 + 0x006E6CC4


class FakeStub(threading.Thread):
    def __init__(self, server):
        super().__init__(daemon=True)
        self.server = server
        self.queries = []
        self.error = None
        self.resumed = False

    @staticmethod
    def frame(payload):
        raw = payload.encode("ascii")
        return b"$" + raw + b"#" + f"{sum(raw) & 255:02x}".encode()

    def run(self):
        try:
            conn, _ = self.server.accept()
            with conn:
                buf = b""
                while True:
                    received = conn.recv(16384)
                    if not received:
                        break
                    buf += received
                    while b"$" in buf and b"#" in buf:
                        start = buf.index(b"$")
                        end = buf.find(b"#", start)
                        if end < 0 or len(buf) < end + 3:
                            break
                        cmd = buf[start + 1:end].decode()
                        buf = buf[end + 3:]
                        self.queries.append(cmd)
                        if cmd == "?":
                            answer = "T05thread:1;"
                        elif cmd.startswith("m"):
                            addr = int(cmd[1:].split(",")[0], 16)
                            vals = {
                                HOOK: struct.pack("<I", 0x1E201828),
                                0x200100: struct.pack("<Q", 10_000_000),
                                0x200148: struct.pack("<Q", 1_000_000),
                                0x200150: struct.pack("<Q", 900_000),
                                0x2002C8: struct.pack("<f", 30.0),
                            }
                            answer = vals[addr].hex()
                        elif cmd == "g":
                            regs = [0] * 33
                            regs[21] = 0x200000
                            regs[32] = HOOK
                            answer = struct.pack("<33QI", *regs, 0).hex()
                        elif cmd.startswith(("Z0", "z0", "Hg")):
                            answer = "OK"
                        elif cmd == "s":
                            answer = "T05thread:1;"
                        elif cmd == "c":
                            if any(q.startswith("z0") for q in self.queries):
                                self.resumed = True
                                continue
                            answer = "T05thread:1;"
                        else:
                            raise AssertionError(cmd)
                        conn.sendall(b"+" + self.frame(answer))
        except Exception as exc:
            self.error = exc


class FakeStubEndToEnd(unittest.TestCase):
    def test_single_observation_resumes_game(self):
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            stub = FakeStub(server)
            stub.start()
            cmd = [
                sys.executable, str(SCRIPT),
                "--build-id", "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348",
                "--main-base", "0x80d3a000", "--phase", "menu", "--immediate",
                "--samples", "1", "--port", str(server.getsockname()[1]),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            stub.join(timeout=2)
            self.assertIsNone(stub.error)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(stub.resumed)
            self.assertIn('"field_100": 10000000', result.stdout)
            self.assertNotIn("0x200000", result.stdout)


if __name__ == "__main__":
    unittest.main()
