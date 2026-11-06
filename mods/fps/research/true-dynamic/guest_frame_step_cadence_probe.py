#!/usr/bin/env python3
"""Sparse numeric-only research probe for Ocarina of Time E0F3 timing state.

NOT a gameplay FPS mod or profiler. At the pristine original fdiv hook,
identify frame context X19, FPS state X21, and rate configuration X20.
Remove the temporary breakpoint, step past original instruction, let the
emulator run for several seconds, and briefly interrupt to read the cached
accumulator and nominal-rate fields. No game-code injections, watchpoints,
patches, original-code dumps, or game-memory writes.

Multiple frame-step paths can update the same rate config and accumulator.
An accumulator delta alone does not prove physical simulation tick counts.
"""
import argparse
import json
import math
from pathlib import Path
import re
import socket
import struct
import time

from guest_timer_probe import HOOKS, RSP, detect_main_base, verify_unmodified_hook

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
COUNTER_HZ = 31_250_000
RATE_GLOBAL_SLOT_OFFSET = 0x04C7E890  # global holder, verified E0F3 instructions


def expected_stop(reply, stage):
    if not reply.startswith(("T", "S")):
        raise RuntimeError(f"Unexpected debugger result at {stage}: {reply[:40]}")


def require_ok(rsp, cmd):
    result = rsp.packet(cmd)
    if result != "OK":
        raise RuntimeError(f"Debugger rejected {cmd.split(',')[0]}: {result[:48]}")


def read_u64(rsp, addr):
    return struct.unpack("<Q", rsp.mem(addr, 8))[0]


def valid_guest_ptr(value):
    return 0x10000 <= value < 1 << 48 and not (value & 7)


def check_object_paths(rsp, base, frame, fps_state, config):
    manager = read_u64(rsp, frame + 0xA8)
    if not valid_guest_ptr(manager) or read_u64(rsp, manager + 0x20) != fps_state:
        raise RuntimeError("Frame-context to FPS-state pointer relationship changed")
    holder = read_u64(rsp, base + RATE_GLOBAL_SLOT_OFFSET)
    if not valid_guest_ptr(holder) or read_u64(rsp, holder) != config:
        raise RuntimeError("Rate-configuration global pointer relationship changed")


def locate_state(rsp, base):
    """Identify state at original hook and ensure breakpoint is removed."""
    if not (0x10000 <= base <= 0xFFFFFFFFFF) or (base & 0xFFF):
        raise ValueError("Invalid current-session main-module base")
    hook = base + HOOKS[BUILD]
    verify_unmodified_hook(rsp, hook)
    armed = False
    try:
        require_ok(rsp, f"Z0,{hook:x},4")
        armed = True
        event = rsp.packet("c")
        expected_stop(event, "original frame-step hook")
        thread = re.search(r"thread:([0-9a-fA-F]+);", event)
        if thread:
            require_ok(rsp, f"Hg{thread.group(1)}")
        regs = rsp.regs()
        if regs.get("pc") != hook:
            raise RuntimeError("Debugger stopped outside original fdiv hook")
        frame, fps_state, config = (regs.get(name, 0) for name in ("x19", "x21", "x20"))
        if not all(valid_guest_ptr(x) for x in (frame, fps_state, config)):
            raise RuntimeError("Invalid frame/rate-state pointer at frame-step hook")
        check_object_paths(rsp, base, frame, fps_state, config)
        require_ok(rsp, f"z0,{hook:x},4")
        armed = False
        expected_stop(rsp.packet("s"), "single-step original fdiv")
        return frame, fps_state, config
    finally:
        if armed:
            try:
                rsp.packet(f"z0,{hook:x},4")
            except Exception:
                pass


def float_field(raw, offset):
    bits = struct.unpack_from("<I", raw, offset)[0]
    value = struct.unpack_from("<f", raw, offset)[0]
    return {"bits": f"0x{bits:08x}", "value": value if math.isfinite(value) else None}


def sample_fields(rsp, base, frame, fps_state, config):
    check_object_paths(rsp, base, frame, fps_state, config)
    flags = struct.unpack("<I", rsp.mem(frame + 0xD38, 4))[0]
    inflight = struct.unpack("<I", rsp.mem(frame + 0xD50, 4))[0]
    double_raw = rsp.mem(frame + 0xD58, 8)
    total = struct.unpack("<d", double_raw)[0]
    timer = rsp.mem(fps_state + 0x100, 16)
    cached_delta, prev_tick = struct.unpack("<QQ", timer)
    target_fps = struct.unpack("<I", rsp.mem(fps_state + 0x2C8, 4))[0]
    rate_data = rsp.mem(config + 0x10, 16)
    return {
        "frame_flags_d38_u32": flags,
        "frame_inflight_d50_u32": inflight,
        "accum_d58_bits": f"0x{struct.unpack('<Q', double_raw)[0]:016x}",
        "accum_d58_f64": total if math.isfinite(total) else None,
        "cached_delta_100_ticks": cached_delta,
        "previous_counter_108_ticks": prev_tick,
        "integer_target_fps_2c8": target_fps,
        "rate_step_10": float_field(rate_data, 0),
        "rate_reciprocal_14": float_field(rate_data, 4),
        "rate_scaled_18": float_field(rate_data, 8),
        "rate_nominal_1c_u32": struct.unpack_from("<I", rate_data, 12)[0],
    }


def summarize_delta(prior, current):
    ticks = current["previous_counter_108_ticks"] - prior["previous_counter_108_ticks"]
    result = {"guest_counter_elapsed_seconds": round(ticks / COUNTER_HZ, 6) if ticks > 0 else None}
    a, b = prior["accum_d58_f64"], current["accum_d58_f64"]
    if ticks > 0 and a is not None and b is not None:
        diff = b - a
        result["accumulator_change_units"] = round(diff, 6)
        result["accumulator_units_per_guest_second_if_no_reset"] = round(diff * COUNTER_HZ / ticks, 6)
    return result


def run_sparse(rsp, base, frame, fps_state, config, count, seconds, *, sleep=time.sleep):
    if not 1 <= count <= 12 or not 2 <= seconds <= 30:
        raise ValueError("Samples must be 1..12 and time intervals 2..30 seconds")
    output = []
    try:
        first = sample_fields(rsp, base, frame, fps_state, config)
        first["sample"] = 0
        output.append(first)
        for i in range(count):
            rsp.send_continue()
            sleep(seconds)
            rsp.sock.sendall(b"\x03")
            expected_stop(rsp.recv_packet(), "sparse timing-state interrupt")
            point = sample_fields(rsp, base, frame, fps_state, config)
            point["sample"] = i + 1
            point["change_since_prior"] = summarize_delta(output[-1], point)
            output.append(point)
            print(f"Snapshot {i + 1}/{count}: nominal rate {point['rate_nominal_1c_u32']}, "
                  f"step {point['rate_step_10']['value']}", flush=True)
        return output
    finally:
        try:
            rsp.send_continue()
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", type=Path, required=True,
                    help="Current-session Eglantine eden_log.txt")
    ap.add_argument("--port", type=int, default=6543)
    ap.add_argument("--fps-label", default="unspecified")
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--seconds-between", type=float, default=4)
    ap.add_argument("--output", type=Path, default=Path("frame_step_cadence.json"))
    args = ap.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.samples <= 12 or not 2 <= args.seconds_between <= 30:
        ap.error("Port 1..65535, samples 1..12, interval 2..30 seconds")
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        running_series = False
        try:
            expected_stop(rsp.packet("?"), "initial guest attach")
            print("Connected. Load a stable gameplay scene, then press Enter here.", flush=True)
            rsp.send_continue()
            input()
            sock.sendall(b"\x03")
            expected_stop(rsp.recv_packet(), "scene-selection interrupt")
            base = detect_main_base(args.log.read_text(errors="replace"))
            frame, fps_state, config = locate_state(rsp, base)
            print("Verified original hook and state pointers; breakpoint removed.", flush=True)
            running_series = True
            samples = run_sparse(rsp, base, frame, fps_state, config,
                                 args.samples, args.seconds_between)
        finally:
            if not running_series:
                try:
                    rsp.send_continue()
                except OSError:
                    pass
    report = {
        "build_id": BUILD,
        "fps_label_user_observed": args.fps_label,
        "guest_counter_hz": COUNTER_HZ,
        "free_run_interval_requested_seconds": args.seconds_between,
        "private": "Numeric research report; do not commit raw debugger results.",
        "limitations": "Accumulator may reset, multiple timing paths may exist, and debugger interrupts "
                       "perturb immediately adjacent frames. This is not a per-present call count.",
        "samples": samples,
    }
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Saved {args.output} (numeric telemetry only). Guest resumed.")


if __name__ == "__main__":
    main()
