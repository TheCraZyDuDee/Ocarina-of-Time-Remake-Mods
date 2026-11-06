#!/usr/bin/env python3
"""Short GDB original-code call-path trace, E0F3 only. No FPS mod.

Records which of the two verified original caller BL sites invokes the
timing-config function, and the live S0/S8 inputs and numeric flags.
Temporary software breakpoints perturb timing; this tool MUST NOT be used
for FPS benchmarking, per-present cadence or elapsed duration estimates.
No game executables, dumps or code bytes are written to JSON.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import socket
import struct

from guest_timer_probe import HOOKS, RSP, detect_main_base, verify_unmodified_hook

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
TARGET = 0x03B4E300
SITES = {
    0x006E6DD8: 0x94D19D4A,
    0x006E70F8: 0x94D19C82,
}


def branch_target(site, word):
    if word & 0xFC000000 != 0x94000000:
        raise ValueError("Not an original AArch64 BL")
    imm = word & 0x3FFFFFF
    if imm & (1 << 25):
        imm -= 1 << 26
    return site + 4 * imm


def expect_stop(packet, stage):
    if not packet.startswith(("T", "S")):
        raise RuntimeError(f"Unexpected debugger stop during {stage}: {packet[:48]}")


def require_ok(rsp, command):
    result = rsp.packet(command)
    if result != "OK":
        raise RuntimeError(f"Debugger rejected {command.split(',')[0]}: {result[:60]}")


def check_sites(rsp, base):
    if not (0x10000 <= base <= 0xFFFFFFFFFF) or base & 0xFFF:
        raise ValueError("Invalid current-session main module base")
    verify_unmodified_hook(rsp, base + HOOKS[BUILD])
    for offset, expected in SITES.items():
        if branch_target(offset, expected) != TARGET:
            raise ValueError("Original callsite does not target expected function")
        actual = struct.unpack("<I", rsp.mem(base + offset, 4))[0]
        if actual != expected:
            raise ValueError(f"Original BL mismatch at main+0x{offset:08x}; no breakpoints set")


def safe_float(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


def capture_hit(rsp, base, regs, pc):
    # X19 is preserved as the frame context. X21 was repurposed prior to
    # both call sites; no guest private addresses are exported.
    frame = regs.get("x19", 0)
    if not (0x10000 <= frame < 1 << 48 and frame % 8 == 0):
        raise RuntimeError("Frame-context pointer invalid at timing-config call")
    # X21 is REUSED as a different global pointer before both call sites.
    # Recover FPS state from the verified X19 context chain, never from X21.
    manager = struct.unpack("<Q", rsp.mem(frame + 0xA8, 8))[0]
    if not (0x10000 <= manager < 1 << 48 and manager % 8 == 0):
        raise RuntimeError("Timing-manager pointer invalid at call site")
    fps = struct.unpack("<Q", rsp.mem(manager + 0x20, 8))[0]
    if not (0x10000 <= fps < 1 << 48 and fps % 8 == 0):
        raise RuntimeError("FPS-state pointer invalid at call site")
    flags = struct.unpack("<I", rsp.mem(frame + 0xD38, 4))[0]
    counter = struct.unpack("<I", rsp.mem(frame + 0xD50, 4))[0]
    nominal = struct.unpack("<I", rsp.mem(fps + 0x2C8, 4))[0]
    return {
        "call_site": f"main+0x{pc-base:08x}",
        "frame_flags_d38_u32": flags,
        "frame_counter_d50_u32": counter,
        "integer_target_fps_2c8": nominal,
        "incoming_s0": safe_float(regs.get("s0")),
        "original_step_s8": safe_float(regs.get("s8")),
        "note": "Breakpoint sample; do not interpret as natural frame timing."
    }


def trace_paths(rsp, base, hits):
    """From a stopped debugger, arm two temporary breakpoints, sample,
    single-step each original call and resume. Always remove all breakpoints.
    """
    if not 1 <= hits <= 12:
        raise ValueError("Hit count must be 1..12")
    armed = set()
    samples = []
    addresses = {base + offset for offset in SITES}
    try:
        check_sites(rsp, base)
        for addr in sorted(addresses):
            require_ok(rsp, f"Z0,{addr:x},4")
            armed.add(addr)
        for index in range(hits):
            stop = rsp.packet("c")
            expect_stop(stop, "timing config callsite")
            match = re.search(r"thread:([0-9a-fA-F]+);", stop)
            if match:
                require_ok(rsp, f"Hg{match.group(1)}")
            regs = rsp.regs()
            pc = regs.get("pc", 0)
            if pc not in addresses:
                raise RuntimeError("Debugger stopped somewhere other than verified call sites")
            samples.append(capture_hit(rsp, base, regs, pc))
            # Step the original call without leaving a breakpoint at PC.
            require_ok(rsp, f"z0,{pc:x},4")
            armed.remove(pc)
            expect_stop(rsp.packet("s"), "original call instruction single-step")
            # Rearm except on final sample.
            if index + 1 < hits:
                require_ok(rsp, f"Z0,{pc:x},4")
                armed.add(pc)
            print(f"Hit {index + 1}/{hits}: main+0x{pc-base:08x}", flush=True)
        return {
            "build_id": BUILD,
            "expected_callee_main_offset": f"main+0x{TARGET:08x}",
            "total_hits": len(samples),
            "hits_by_call_site": dict(Counter(x["call_site"] for x in samples)),
            "hits": samples,
            "limitations": "Breakpoint processing delays guest frames and may affect branch state. "
                           "No FPS, update-call frequency, or physics cadence inference is valid.",
        }
    finally:
        for addr in sorted(armed):
            try:
                rsp.packet(f"z0,{addr:x},4")
            except Exception:
                pass
        try:
            rsp.send_continue()
        except OSError:
            pass


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", type=Path, required=True,
                   help="Current-launch Eglantine eden_log.txt")
    p.add_argument("--port", type=int, default=6543)
    p.add_argument("--hits", type=int, default=8)
    p.add_argument("--output", type=Path, default=Path("frame_step_paths.json"))
    args = p.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.hits <= 12:
        p.error("Port 1..65535, hits 1..12")
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        trace_started = False
        try:
            expect_stop(rsp.packet("?"), "initial debugger halt")
            print("Connected. Load stable gameplay, then press Enter here.", flush=True)
            rsp.send_continue()
            input()
            sock.sendall(b"\x03")
            expect_stop(rsp.recv_packet(), "manual scene-selection interrupt")
            base = detect_main_base(args.log.read_text(errors="replace"))
            trace_started = True
            report = trace_paths(rsp, base, args.hits)
        finally:
            if not trace_started:
                try:
                    rsp.send_continue()
                except OSError:
                    pass
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Saved numeric-only private report: {args.output}. Game resumed.")


if __name__ == "__main__":
    main()
