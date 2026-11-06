#!/usr/bin/env python3
"""Collect sparse timer-field snapshots after uninterrupted gameplay periods.

E0F3 only. NOT a mod, FPS profiler, game patch or unattended monitor.
The local GDB stub is used to identify x21 once at the original frame-step
hook, remove the temporary debugger breakpoint, step the original instruction,
then resume gameplay for several seconds between brief manual interrupts.
Do not interpret interrupted-frame values as unbiased per-frame measures.

The output is private numeric telemetry (no Nintendo code or raw game memory).
Use with an unmodified game, all FPS mods disabled, current-session main base.
"""
import argparse
import json
import re
from pathlib import Path
import socket
import struct
import time

from guest_timer_probe import HOOKS, RSP, detect_main_base, verify_unmodified_hook

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
COUNTER_HZ = 31_250_000  # Confirmed physical counter frequency for this guest.
WINDOW_SIZE = 0x58  # offsets +0x100 to +0x157 inclusive; no game code bytes.


def expect_stop(reply, context):
    if not reply.startswith(("T", "S")):
        raise RuntimeError(f"Unexpected GDB reply during {context}: {reply[:50]}")


def gdb_ok(rsp, cmd):
    reply = rsp.packet(cmd)
    if reply != "OK":
        raise RuntimeError(f"Debugger rejected {cmd.split(',')[0]}: {reply[:60]}")


def locate_state(rsp, base):
    """Get x21 from a verified original frame-step hook, then unhook safely."""
    if base < 0x10000 or base >= (1 << 48) or (base & 0xFFF):
        raise ValueError("Invalid current main module base")
    hook = base + HOOKS[BUILD]
    verify_unmodified_hook(rsp, hook)
    armed = False
    try:
        gdb_ok(rsp, f"Z0,{hook:x},4")
        armed = True
        stop = rsp.packet("c")
        expect_stop(stop, "first original frame-step")
        match = re.search(r"thread:([0-9a-fA-F]+);", stop)
        if match:
            gdb_ok(rsp, f"Hg{match.group(1)}")
        registers = rsp.regs()
        if registers.get("pc") != hook:
            raise RuntimeError("Stopped outside the verified original frame-step hook")
        state = registers.get("x21", 0)
        if not 0x10000 <= state < (1 << 48) or state & 7:
            raise RuntimeError("Frame-state pointer is invalid")
        identity = struct.unpack("<Q", rsp.mem(state, 8))[0]
        if not identity or identity & 7:
            raise RuntimeError("Frame-state identity pointer is invalid")
        gdb_ok(rsp, f"z0,{hook:x},4")
        armed = False
        expect_stop(rsp.packet("s"), "stepping past original frame-step")
        return state, identity
    finally:
        if armed:
            try:
                rsp.packet(f"z0,{hook:x},4")
            except Exception:
                pass


def snapshot_state(rsp, state, identity):
    if struct.unpack("<Q", rsp.mem(state, 8))[0] != identity:
        raise RuntimeError("Frame-state identity changed: abort rather than read a stale object")
    raw = rsp.mem(state + 0x100, WINDOW_SIZE)
    if len(raw) != WINDOW_SIZE:
        raise RuntimeError("Incomplete timing-state snapshot")
    duration, previous, partial, accumulator = (struct.unpack_from("<Q", raw, x)[0]
                                                for x in (0, 8, 0x48, 0x50))
    return {
        "elapsed_100_u64": duration,
        "elapsed_100_ms_if_guest_counter_ticks": round(duration * 1000 / COUNTER_HZ, 3),
        "previous_108_u64": previous,
        "partial_148_u64": partial,
        "field_150_u64": accumulator,
        "would_saturate_v9_at_60hz": duration >= (4 * COUNTER_HZ / 60),
    }


def collect_snapshots(rsp, state, identity, samples, seconds_between, *, sleep=time.sleep):
    """Interrupt only after a free-running interval; always resume on exit."""
    if not 1 <= samples <= 12 or not 2 <= seconds_between <= 30:
        raise ValueError("Invalid sample count or free-run interval")
    result = []
    try:
        for index in range(samples):
            rsp.send_continue()
            sleep(seconds_between)
            rsp.sock.sendall(b"\x03")
            expect_stop(rsp.recv_packet(), f"sparse snapshot {index + 1}")
            point = snapshot_state(rsp, state, identity)
            point["sample"] = index + 1
            result.append(point)
        return result
    finally:
        try:
            rsp.send_continue()
        except OSError:
            pass


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", type=Path, required=True,
                   help="Current-launch Eglantine eden_log.txt")
    p.add_argument("--port", type=int, default=6543)
    p.add_argument("--phase", choices=("menu", "gameplay"), default="gameplay")
    p.add_argument("--fps-label", default="unspecified",
                   help="Your own approximate FPS overlay reading, not debugger-measured")
    p.add_argument("--samples", type=int, default=5)
    p.add_argument("--seconds-between", type=float, default=4.0)
    p.add_argument("--output", type=Path, default=Path("quiet_timer_snapshots.json"))
    args = p.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.samples <= 12 or not 2 <= args.seconds_between <= 30:
        p.error("Port 1..65535, samples 1..12, interval 2..30 seconds")
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        try:
            expect_stop(rsp.packet("?"), "initial debugger attachment")
            print(f"Connected. Load a stable {args.phase} scene; press Enter here to begin.", flush=True)
            rsp.send_continue()
            input()
            sock.sendall(b"\x03")
            expect_stop(rsp.recv_packet(), "scene-selection interrupt")
            base = detect_main_base(args.log.read_text(errors="replace"))
            state, identity = locate_state(rsp, base)
            print("Frame state identified. Temporary breakpoint removed. Taking sparse snapshots.", flush=True)
            samples = collect_snapshots(rsp, state, identity, args.samples, args.seconds_between)
        finally:
            try:
                rsp.send_continue()
            except OSError:
                pass
    report = {
        "build_id": BUILD, "phase": args.phase,
        "fps_label_user_observed": args.fps_label,
        "free_running_seconds_between_samples": args.seconds_between,
        "guest_counter_hz": COUNTER_HZ,
        "note": "Sparse samples after free run; debugger interrupts can still perturb timing."
                " Do not infer frame cadence solely from this report.",
        "samples": samples,
    }
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("Saved private numeric report:", args.output, "; game resumed.")


if __name__ == "__main__":
    main()
