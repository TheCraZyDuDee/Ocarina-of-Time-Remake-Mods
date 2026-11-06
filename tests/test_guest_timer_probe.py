"""Synthetic tests for the read-only GDB timer probe (no game assets)."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

path = (Path(__file__).resolve().parents[1] / "mods" / "fps" /
        "research" / "true-dynamic" / "guest_timer_probe.py")
spec = importlib.util.spec_from_file_location("guest_timer_probe", path)
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


class FakeSocket:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = bytearray()

    def sendall(self, value):
        self.sent.extend(value)

    def recv(self, length):
        return self.responses.pop(0) if self.responses else b""


def frame(value):
    payload = value.encode("ascii")
    return b"+" + b"$" + payload + b"#" + f"{sum(payload) & 255:02x}".encode()


class ProbeTest(unittest.TestCase):
    def test_packet_checksum_and_ack(self):
        sock = FakeSocket([frame("OK")])
        self.assertEqual(probe.RSP(sock).packet("Z0,10,4"), "OK")
        self.assertIn(b"$Z0,10,4#", sock.sent)
        self.assertTrue(sock.sent.endswith(b"+"))

    def test_bad_checksum(self):
        sock = FakeSocket([b"$OK#00"])
        with self.assertRaisesRegex(ValueError, "checksum"):
            probe.RSP(sock).recv_packet()
        self.assertTrue(sock.sent.endswith(b"-"))

    def test_64bit_registers(self):
        values = list(range(33))
        raw = struct.pack("<33QI", *values, 0x200001C5).hex()
        result = probe.RSP(FakeSocket([frame(raw)])).regs()
        self.assertEqual(result["x21"], 21)
        self.assertEqual(result["pc"], 32)
        self.assertEqual(result["cpsr"], 0x200001C5)

    def test_actual_fdiv_operands_from_vector_registers(self):
        gprs = [0] * 33
        gprs[21] = 0x200000
        gprs[32] = 0x816E6CC4
        vector = bytearray(32 * 16)
        struct.pack_into("<f", vector, 0 * 16, 30.0)
        struct.pack_into("<f", vector, 1 * 16, 60.0)
        struct.pack_into("<f", vector, 8 * 16, 2.0)
        payload = struct.pack("<33QI", *gprs, 0) + bytes(vector)
        parsed = probe.RSP(FakeSocket([frame(payload.hex())])).regs()
        self.assertEqual(parsed["s0"], 30.0)
        self.assertEqual(parsed["s1"], 60.0)
        self.assertEqual(parsed["s8"], 2.0)
        self.assertEqual(parsed["s0_bits"], 0x41F00000)

    def test_memory(self):
        value = probe.RSP(FakeSocket([frame("1122334455667788")])).mem(0x1000, 8)
        self.assertEqual(value, bytes.fromhex("1122334455667788"))

    def test_field_sampling(self):
        class Mem:
            def mem(self, addr, size):
                data = {
                    0x200100: struct.pack("<Q", 45_000_000),
                    0x200148: struct.pack("<Q", 1_000_000),
                    0x200150: struct.pack("<Q", 900_000),
                    0x2002C8: struct.pack("<f", 30.0),
                }
                return data[addr]
        value = probe.parse_guest_sample(Mem(), {"x21": 0x200000})
        self.assertEqual(value["field_100"], 45_000_000)
        self.assertEqual(value["field_2c8_raw_u32"], struct.unpack("<I", struct.pack("<f",30.0))[0])

    def test_raw_60_is_not_float_60(self):
        class Mem:
            def mem(self, addr, size):
                if addr == 0x2002C8:
                    return struct.pack("<I",60)
                return struct.pack("<Q",1_000_000)
        sample = probe.parse_guest_sample(
            Mem(), {"x21":0x200000, "s0":30.0,
                     "s0_bits":0x41F00000, "s1":60.0,
                     "s1_bits":0x42700000, "s8":2.0,
                     "s8_bits":0x40000000})
        self.assertEqual(sample["field_2c8_raw_u32"], 60)
        self.assertLess(sample["field_2c8_float_interpretation"],1e-40)
        self.assertEqual(sample["fdiv_denominator_s0"],30.0)
        self.assertEqual(sample["fdiv_numerator_s1"],60.0)

    def test_saturation_pattern(self):
        samples = [{
            "field_100": 3_000_000 + index * 500_000,
            "field_148": 1_000_000 + index,
            "field_150": 1000,
            "target_fps": 30.0,
        } for index in range(4)]
        result = probe.determine_patterns(samples)
        self.assertTrue(result["field_100"]["saturates_v9_clamp_at_60hz"])
        self.assertEqual(result["field_100"]["min_difference"], 500_000)
        self.assertEqual(result["field_150"]["changes"], 0)

    def test_original_instruction_guard(self):
        class Mem:
            def __init__(self, opcode):
                self.opcode = opcode
            def mem(self, addr, n):
                return struct.pack("<I", self.opcode)
        probe.verify_unmodified_hook(Mem(0x1E201828), 0x8000)
        report = probe.inspect_hook_identity(
            Mem(0x14000004), 0x80D3A000,
            "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
        )
        self.assertFalse(report["original_hook_matches"])
        self.assertEqual(report["observed_instruction"], "0x14000004")
        with self.assertRaisesRegex(ValueError, "observed 0x14000004"):
            probe.verify_unmodified_hook(Mem(0x14000004), 0x8000)

    def test_log_resolution(self):
        value = probe.detect_main_base(
            "[0.3] Loader: Module main loaded at 0x80d3a000 (size 0x4ea0000)\n"
            "[0.4] Loader: Moduusere main useroaded at 0x90d3a000 (size 0x4ea0000)"
        )
        self.assertEqual(value, 0x90d3a000)
        with self.assertRaises(ValueError):
            probe.detect_main_base("Module sdk loaded at 0x80000 (size 0x100)")

    def test_builds_and_original_hook(self):
        self.assertEqual(len(probe.HOOKS), 2)
        self.assertEqual(probe.ORIGINAL_HOOK_INSN, 0x1E201828)


if __name__ == "__main__":
    unittest.main()
