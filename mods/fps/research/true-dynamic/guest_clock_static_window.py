#!/usr/bin/env python3
"""Private read-only guest-code window around the E0F3 clock-call target.

This is NOT a gameplay mod. At the initial debugger halt, verify the
unaltered frame-step and known writer instructions, read a bounded clock
routine excerpt, then resume the emulator. The JSON contains original game
code: never commit or publish it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct

from guest_timer_probe import HOOKS, RSP, detect_main_base, read_hook_word, verify_unmodified_hook

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
WRITER_OFFSET = 0x0346C7EC
WRITER_STORE = 0xF9008268  # verified str x8, [x19, #0x100]
CLOCK_OFFSET = 0x03C41FD0  # four direct BL calls from the private writer window
BEFORE = 0x40
AFTER = 0x200


def capture_window(rsp, base, *, build_id=BUILD):
    """Verify known code before reading any new original instruction window."""
    if build_id != BUILD:
        raise ValueError("Clock target has only been mapped on E0F3")
    if not 0x10000 <= base <= 0xFFFFFFFFFF or base & 3:
        raise ValueError("Invalid main module base")
    verify_unmodified_hook(rsp, base + HOOKS[BUILD])
    actual = read_hook_word(rsp, base + WRITER_OFFSET)
    if actual != WRITER_STORE:
        raise ValueError(
            f"Original timer writer mismatch at main+0x{WRITER_OFFSET:08x}: "
            f"expected 0x{WRITER_STORE:08x}, got 0x{actual:08x}. "
            "Stop; confirm current launch, original main build, and disabled patches."
        )
    size = BEFORE + AFTER
    if size > 4096 or (size & 3):
        raise ValueError("Unbounded or unaligned clock window")
    start = CLOCK_OFFSET - BEFORE
    raw = rsp.mem(base + start, size)
    if len(raw) != size or not any(raw):
        raise ValueError("Clock routine is not mapped")
    words = struct.unpack("<" + "I" * (size // 4), raw)
    return {
        "build_id": build_id,
        "clock_call_target_main_offset": f"main+0x{CLOCK_OFFSET:08x}",
        "window_first_main_offset": f"main+0x{start:08x}",
        "clock_target_word_index": BEFORE // 4,
        "instruction_words_u32_le": [f"0x{w:08x}" for w in words],
        "sha256_window": hashlib.sha256(raw).hexdigest(),
        "private": "Original game instruction excerpt. Do not commit, publish, or distribute.",
        "note": "Static clock target only. Timer units and per-present timing remain unverified.",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", type=Path, required=True, help="CURRENT launch eden_log.txt")
    ap.add_argument("--port", type=int, default=6543)
    ap.add_argument("--output", type=Path, default=Path("clock_source_window.json"))
    args = ap.parse_args()
    if not 1 <= args.port <= 65535:
        ap.error("Port must be in 1..65535")
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        try:
            stopped = rsp.packet("?")
            if not stopped.startswith(("T", "S")):
                raise RuntimeError("Guest is not stopped. Restart Eglantine with GDB Stub enabled.")
            base = detect_main_base(args.log.read_text(errors="replace"))
            report = capture_window(rsp, base)
        finally:
            try:
                rsp.send_continue()
            except OSError:
                pass
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2)
    print(f"Saved private clock instruction excerpt to {args.output}; guest resumed.")
    print("Upload ONLY the private JSON here. Never publish it to GitHub.")


if __name__ == "__main__":
    main()
