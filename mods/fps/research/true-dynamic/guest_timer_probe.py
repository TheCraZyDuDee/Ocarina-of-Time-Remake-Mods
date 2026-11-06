#!/usr/bin/env python3
"""Read-only GDB-stub experiment: sample OoT's suspected timer field.

Not a patch/mod. Stops the guest on the *original* frame-step instruction,
reads three integer fields and one FPS float from a guest object, single-steps
past the original instruction, then resumes. Tracing necessarily perturbs
frame timing, so DO NOT use the sample for FPS or real-time speed benchmarks.

Outputs only raw numeric field values (not memory dumps or addresses). Uses
only Python stdlib and local 127.0.0.1. No game files or saves are accessed.
"""
import argparse
import json
import math
from pathlib import Path
import re
import socket
import struct
import sys
import time

HOOKS = {
    "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348": 0x006E6CC4,
    "33FA6C2C23848282A77E8B88A0A93F4887C55920": 0x006B5A08,
}
REGS = [f"x{i}" for i in range(31)] + ["sp", "pc", "cpsr"]
ORIGINAL_HOOK_INSN = 0x1E201828  # fdiv s8,s1,s0 (from original binary)
READ_SIZES = {"field_100": (0x100, 8), "field_148": (0x148, 8),
              "field_150": (0x150, 8), "target_fps": (0x2C8, 4)}


class RSP:
    def __init__(self, sock):
        self.sock = sock
        self.buf = b""

    def packet(self, command):
        command = command.encode("ascii")
        self.sock.sendall(b"$" + command + b"#" + f"{sum(command) & 255:02x}".encode())
        return self.recv_packet()

    def send_continue(self):
        command = b"c"
        self.sock.sendall(b"$" + command + b"#" + f"{sum(command) & 255:02x}".encode())

    def recv_packet(self):
        while True:
            self.buf = self.buf.lstrip(b"+-")
            p = self.buf.find(b"$")
            if p >= 0:
                h = self.buf.find(b"#", p + 1)
                if h >= 0 and len(self.buf) >= h + 3:
                    payload = self.buf[p + 1:h]
                    checksum = self.buf[h + 1:h + 3]
                    self.buf = self.buf[h + 3:]
                    if (sum(payload) & 255) != int(checksum, 16):
                        self.sock.sendall(b"-")
                        raise ValueError("Bad debugger packet checksum")
                    self.sock.sendall(b"+")
                    return payload.decode("ascii", errors="replace")
            chunk = self.sock.recv(16384)
            if not chunk:
                raise ConnectionError("Debugger disconnected")
            self.buf += chunk
            if len(self.buf) > 4 * 1024 * 1024:
                raise ValueError("Unexpected large debugger response")

    def regs(self):
        raw = self.packet("g")
        try:
            data = bytes.fromhex(raw)
        except ValueError as exc:
            raise ValueError(f"Debugger did not return AArch64 registers: {raw[:12]}") from exc
        if len(data) < 8 * 33 + 4:
            raise ValueError("Incomplete AArch64 register reply")
        d = dict(zip(REGS[:33], struct.unpack_from("<33Q", data)))
        d["cpsr"] = struct.unpack_from("<I", data, 33 * 8)[0]
        return d

    def mem(self, guest_addr, size):
        if guest_addr <= 0 or size <= 0 or size > 4096:
            raise ValueError("Invalid read-only guest memory request")
        response = self.packet(f"m{guest_addr:x},{size:x}")
        try:
            raw = bytes.fromhex(response)
        except ValueError as exc:
            raise ValueError(f"Guest memory read failed: {response[:12]}") from exc
        if len(raw) != size:
            raise ValueError("Guest memory read returned unexpected length")
        return raw


def detect_main_base(log_text):
    """Return the newest main NSO load base, tolerating emulator log prefixes."""
    matches = []
    for line in log_text.splitlines():
        if "main" not in line or "size" not in line:
            continue
        m = re.search(r"\bmain\s+\w+\s+at\s+0x([0-9a-fA-F]+)\s+\(size", line)
        if m:
            matches.append(int(m.group(1), 16))
    if not matches:
        raise ValueError("No main module load base found in log")
    return matches[-1]


def read_hook_word(rsp, guest_address):
    """Read one original guest instruction; never change the guest code."""
    return struct.unpack("<I", rsp.mem(guest_address, 4))[0]


def verify_unmodified_hook(rsp, guest_address):
    """Fail closed and report the exact mismatch for debugging stale addresses."""
    actual = read_hook_word(rsp, guest_address)
    if actual != ORIGINAL_HOOK_INSN:
        raise ValueError(
            f"Original timing instruction mismatch at guest 0x{guest_address:x}: "
            f"expected 0x{ORIGINAL_HOOK_INSN:08x}, observed 0x{actual:08x}. "
            "Do not bypass this guard. Confirm this game's CURRENT main load "
            "address from the current-session eden_log.txt, correct game build, "
            "and disabled FPS IPS mods. A log from a previous launch may be stale."
        )


def inspect_hook_identity(rsp, base, build_id):
    """Read-only preflight: prints precise identity data without a breakpoint."""
    guest_address = base + HOOKS[build_id]
    word = read_hook_word(rsp, guest_address)
    return {"build_id": build_id, "main_base": f"0x{base:x}",
            "hook_guest_address": f"0x{guest_address:x}",
            "expected_instruction": f"0x{ORIGINAL_HOOK_INSN:08x}",
            "observed_instruction": f"0x{word:08x}",
            "original_hook_matches": word == ORIGINAL_HOOK_INSN}


def parse_guest_sample(rsp, regs):
    """x21 is the FPS-state pointer at the *verified original* hook."""
    base = regs.get("x21", 0)
    if not base or base & 7:
        raise ValueError("Invalid frame-state pointer at breakpoint")
    data = {name: rsp.mem(base + offset, size)
            for name, (offset, size) in READ_SIZES.items()}
    fps = struct.unpack("<f", data["target_fps"])[0]
    if not math.isfinite(fps):
        raise ValueError("FPS target is not a finite float")
    return {"field_100": struct.unpack("<Q", data["field_100"])[0],
            "field_148": struct.unpack("<Q", data["field_148"])[0],
            "field_150": struct.unpack("<Q", data["field_150"])[0],
            "target_fps": fps}


def determine_patterns(samples):
    """Describe values without pretending to know their units."""
    out = {}
    for key in ("field_100", "field_148", "field_150"):
        values = [s[key] for s in samples]
        diffs = [b - a for a, b in zip(values, values[1:])]
        out[key] = {
            "first": values[0], "last": values[-1],
            "changes": sum(a != b for a, b in zip(values, values[1:])),
            "nondecreasing": all(d >= 0 for d in diffs),
            "min_difference": min(diffs) if diffs else None,
            "max_difference": max(diffs) if diffs else None,
            "saturates_v9_clamp_at_60hz": all(v >= 4 * 31_250_000 / 60 for v in values),
        }
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build-id", required=True, choices=sorted(HOOKS))
    locator = p.add_mutually_exclusive_group(required=True)
    locator.add_argument("--main-base", help="Guest main module LOAD BASE, e.g. 0x8000000")
    locator.add_argument("--log", type=Path, help="Private current-session emulator log to find main load base")
    p.add_argument("--port", type=int, default=6543)
    p.add_argument("--samples", type=int, default=12)
    p.add_argument("--phase", required=True, choices=("menu", "gameplay"))
    p.add_argument("--output", default="", help="Optional local JSON output; PRIVATE")
    p.add_argument("--immediate", action="store_true", help="Arm at current guest stop (no menu/gameplay selection)")
    p.add_argument("--check-hook", action="store_true", help="Read original hook opcode, never set a breakpoint; run directly after starting Eglantine")
    args = p.parse_args()
    if not 1 <= args.samples <= 40 or not 1 <= args.port <= 65535:
        p.error("samples must be 1..40 and port 1..65535")
    if args.main_base:
        try:
            base = int(args.main_base, 0)
        except ValueError as exc:
            p.error(f"Invalid main module address: {exc}")
    else:
        base = None   # Resolve the *current* log after the user loads a menu/scene.
    if base is not None and (base < 0x10000 or base & 3):
        p.error("main-base must be an aligned mapped guest address")
    hook = None
    samples = []
    armed = False
    resumed = False
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        try:
            state = rsp.packet("?")
            if not state.startswith(("T", "S")):
                raise ValueError("Debugger has no stopped guest process. Start the game first.")
            if not args.immediate and not args.check_hook:
                print("Debugger attached. Guest will run; load the desired", args.phase,
                      "scene. Press ENTER in this terminal to sample it.", flush=True)
                rsp.send_continue()
                input()
                sock.sendall(b"\x03")  # GDB remote interrupt, not a guest patch.
                if not rsp.recv_packet().startswith(("T", "S")):
                    raise ValueError("Unexpected interrupt response")
            if base is None:
                try:
                    base = detect_main_base(args.log.read_text(errors="replace"))
                except (ValueError, OSError) as exc:
                    raise ValueError(f"Could not locate loaded main module in session log: {exc}") from exc
                if base < 0x10000 or base & 3:
                    raise ValueError("Invalid main module address in log")
            hook = base + HOOKS[args.build_id]
            if args.check_hook:
                report = inspect_hook_identity(rsp, base, args.build_id)
                print(json.dumps(report, indent=2), flush=True)
                if not report["original_hook_matches"]:
                    print("Diagnostic only: this does not prove an FPS mod was enabled. "
                          "Check the current main module base first.", flush=True)
                rsp.send_continue()
                resumed = True
                return
            verify_unmodified_hook(rsp, hook)
            reply = rsp.packet(f"Z0,{hook:x},4")
            if reply != "OK":
                raise ValueError("Breakpoint refused: verify build ID and main LOAD BASE")
            armed = True
            for index in range(args.samples):
                state = rsp.packet("c")
                if not state.startswith(("T", "S")):
                    raise ValueError("Unexpected guest stop response")
                tid = re.search(r"thread:([0-9a-f]+);", state)
                if tid:
                    rsp.packet("Hg" + tid.group(1))
                regs = rsp.regs()
                if regs["pc"] != hook:
                    raise ValueError("Guest stopped elsewhere; disabling trace")
                samples.append(parse_guest_sample(rsp, regs))
                # Only step after restoring the unmodified original instruction.
                if rsp.packet(f"z0,{hook:x},4") != "OK":
                    raise ValueError("Failed to remove breakpoint")
                armed = False
                state = rsp.packet("s")
                if not state.startswith(("T", "S")):
                    raise ValueError("Unexpected single-step reply")
                if index + 1 < args.samples:
                    if rsp.packet(f"Z0,{hook:x},4") != "OK":
                        raise ValueError("Failed to restore breakpoint")
                    armed = True
            # The final single-step leaves the guest paused. Resume it without
            # blocking for a reply (normal 'c' never responds until next stop).
            rsp.send_continue()
            resumed = True
        finally:
            if armed:
                try:
                    rsp.packet(f"z0,{hook:x},4")
                except Exception:
                    pass
            if not resumed:
                try:
                    rsp.send_continue()
                except Exception:
                    pass
    if not samples:
        raise ValueError("No debugger samples")
    out = {"build_id": args.build_id, "phase": args.phase,
           "note": "Breakpoint sampling perturbs frame timing; values' units are UNVERIFIED",
           "samples": samples, "summary": determine_patterns(samples)}
    if args.output:
        with open(args.output, "x", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    print("Only field values saved. No game files, memory dump, keys or addresses recorded.")


if __name__ == "__main__":
    main()
