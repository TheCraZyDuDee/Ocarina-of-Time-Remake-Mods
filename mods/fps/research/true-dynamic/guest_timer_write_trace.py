#!/usr/bin/env python3
"""Local, opt-in GDB-stub investigation of the writer of a suspected time field.

NOT a mod, trainer or runtime FPS profiler. Samples only a bounded number of
write watchpoints to one aligned 64-bit field in the previously verified game
state; pauses guest execution and prints only numeric values and code locations.
Requires a compatible Eglantine GDB stub (watchpoint Z2 support), with the
unmodified original game executable and no FPS mod. Stdlib only.
"""
import argparse
import json
from pathlib import Path
import re
import socket
import struct

from guest_timer_probe import (
    HOOKS, ORIGINAL_HOOK_INSN, RSP, detect_main_base,
    verify_unmodified_hook,
)

ALLOWED_FIELDS = {0x100, 0x148, 0x150}
MAIN_MAX_SIZE = 0x4EA0000  # verified E0F3 loaded-module size in tester's log


def stop_thread_id(reason):
    m = re.search(r"thread:([0-9a-fA-F]+);", reason)
    return m.group(1) if m else None


def expect_stop(reason, purpose):
    if not reason.startswith(("T", "S")):
        raise RuntimeError(f"Unexpected debugger reply during {purpose}: {reason[:80]}")


def send_ok(rsp, cmd):
    response = rsp.packet(cmd)
    if response != "OK":
        raise RuntimeError(f"Debugger rejected {cmd.split(',')[0]}: {response[:40]}")


def identify_location(pc, base):
    if base <= pc < base + MAIN_MAX_SIZE:
        return f"main+0x{pc-base:08x}"
    return "outside_main_module"


def trace_writes(rsp, *, base, build_id, offset=0x100, hits=4):
    """Operate on an already stopped guest, leave it resumed after success.

    A temporary opcode breakpoint discovers x21 (actual state pointer), then
    a read-only hardware/software *write* watchpoint observes who writes
    x21+offset. Watchpoint may report PRE- or POST-store values depending on
    fork implementation, so output does not claim which phase is seen.
    """
    if offset not in ALLOWED_FIELDS or hits not in range(1, 9):
        raise ValueError("Unsupported field offset or write count")
    hook = base + HOOKS[build_id]
    verify_unmodified_hook(rsp, hook)
    breakpoint_armed = False
    watcher_armed = False
    addr = None
    completed = False
    result = []
    initial = None
    try:
        send_ok(rsp, f"Z0,{hook:x},4")
        breakpoint_armed = True
        stop = rsp.packet("c")
        expect_stop(stop, "locating state")
        tid = stop_thread_id(stop)
        if tid:
            send_ok(rsp, f"Hg{tid}")
        regs = rsp.regs()
        if regs["pc"] != hook:
            raise RuntimeError("Target stopped outside original frame-step hook")
        state_base = regs.get("x21", 0)
        if state_base < 0x10000 or state_base & 7:
            raise RuntimeError("Frame-step state pointer is invalid")
        addr = state_base + offset
        initial = struct.unpack("<Q", rsp.mem(addr, 8))[0]
        send_ok(rsp, f"z0,{hook:x},4")
        breakpoint_armed = False
        expect_stop(rsp.packet("s"), "stepping past original instruction")
        send_ok(rsp, f"Z2,{addr:x},8")
        watcher_armed = True
        for _ in range(hits):
            try:
                stop = rsp.packet("c")
            except socket.timeout as exc:
                # Interrupt a long-running guest before clearing its watchpoint.
                # A register or memory operation while guest is running is not
                # guaranteed to be accepted by the GDB stub.
                rsp.sock.sendall(b"\x03")
                rsp.sock.settimeout(10)
                try:
                    expect_stop(rsp.recv_packet(), "watchpoint timeout interrupt")
                except Exception as stop_exc:
                    raise RuntimeError(
                        "Watchpoint timed out and debugger did not confirm a stop. "
                        "Close/restart the emulator before running more diagnostics."
                    ) from stop_exc
                raise RuntimeError(
                    "No write to the selected field within 60 seconds; "
                    "watchpoint cleanup is being attempted."
                ) from exc
            expect_stop(stop, "watchpoint")
            # The debugger may break elsewhere; do not silently report as a
            # successful watch event, especially if another debug client is used.
            if "watch:" not in stop and "awatch:" not in stop:
                raise RuntimeError("Guest stopped without the expected field-write watchpoint")
            tid = stop_thread_id(stop)
            if tid:
                send_ok(rsp, f"Hg{tid}")
            regs = rsp.regs()
            value = struct.unpack("<Q", rsp.mem(addr, 8))[0]
            result.append({
                "writer_code_location": identify_location(regs["pc"], base),
                "observed_field_u64": value,
                "value_relative_to_initial": value - initial,
                "trigger_kind": "write_watchpoint",
            })
            send_ok(rsp, f"z2,{addr:x},8")
            watcher_armed = False
            expect_stop(rsp.packet("s"), "stepping past watched instruction")
            if len(result) < hits:
                send_ok(rsp, f"Z2,{addr:x},8")
                watcher_armed = True
        # Removing the final watchpoint and stepping past it means the next
        # ordinary continue can run with no intervention.
        rsp.send_continue()
        completed = True
        return {"field_offset": f"+0x{offset:x}",
                "initial_field_u64": initial,
                "observations": result,
                "note": "Debugger watchpoints perturb timing; observed values may be before or after writes. Locations outside main require separate module mapping."}
    finally:
        if watcher_armed and addr is not None:
            try:
                rsp.packet(f"z2,{addr:x},8")
            except Exception:
                pass
        if breakpoint_armed:
            try:
                rsp.packet(f"z0,{hook:x},4")
            except Exception:
                pass
        if not completed:
            try:
                # Best effort; debugger may be in a mid-flight c request.
                rsp.send_continue()
            except Exception:
                pass


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build-id", required=True, choices=sorted(HOOKS))
    p.add_argument("--log", required=True, type=Path, help="current-session Eglantine eden_log.txt")
    p.add_argument("--port", type=int, default=6543)
    p.add_argument("--phase", choices=("menu", "gameplay"), default="gameplay")
    p.add_argument("--offset", default="0x100", choices=("0x100", "0x148", "0x150"))
    p.add_argument("--hits", type=int, default=4)
    p.add_argument("--output", type=Path, default=Path("time_field_writes.json"))
    args = p.parse_args()
    if not 1 <= args.hits <= 8 or not 1 <= args.port <= 65535:
        p.error("hits must be 1..8, port must be 1..65535")
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(60)
        rsp = RSP(sock)
        expect_stop(rsp.packet("?"), "initial attachment")
        print(f"Connected. Load your chosen {args.phase} scene in Eglantine, then press Enter here.", flush=True)
        rsp.send_continue()
        input()
        sock.sendall(b"\x03")
        expect_stop(rsp.recv_packet(), "requested sampling halt")
        try:
            # Read log *after* the guest is running: the main load address
            # can differ between launches.
            base = detect_main_base(args.log.read_text(errors="replace"))
        except OSError as e:
            rsp.send_continue()
            raise RuntimeError(f"Could not read current emulator log: {e}") from e
        report = trace_writes(rsp, base=base, build_id=args.build_id,
                              offset=int(args.offset, 16), hits=args.hits)
    report.update({"build_id": args.build_id, "phase": args.phase})
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2)
    print(json.dumps(report, indent=2))
    print(f"Local diagnostic saved: {args.output} (no game bytes or memory dumps)")


if __name__ == "__main__":
    main()
