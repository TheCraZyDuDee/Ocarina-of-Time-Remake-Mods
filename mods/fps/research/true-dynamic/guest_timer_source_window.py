#!/usr/bin/env python3
"""Read-only private E0F3 clock-helper inspection through Eglantine's GDB stub.

Captures 384 bytes at the statically derived target of the timer calls near
the observed +0x100 writer. This is NOT a game patch. The private JSON
contains original game code words and must never be published.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct

from guest_timer_probe import HOOKS, RSP, detect_main_base, verify_unmodified_hook

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
WRITER_OFFSET = 0x0346C7EC
WRITER_OPCODE = 0xF9008268  # str x8, [x19,#0x100]
TIMER_OFFSET = 0x03C41FD0  # BL target at main+0x0346c7e0
TIMER_SIZE = 0x180


def capture_timer_source(rsp, base, build_id=BUILD):
    if build_id != BUILD:
        raise ValueError("Timer source has only been located for E0F3")
    if not (0x10000 <= base <= 0xFFFFFFFFFF) or base & 3:
        raise ValueError("Invalid current main module base")
    verify_unmodified_hook(rsp, base + HOOKS[build_id])
    writer = struct.unpack("<I", rsp.mem(base + WRITER_OFFSET, 4))[0]
    if writer != WRITER_OPCODE:
        raise ValueError("Writer opcode mismatch; stale base, other build, or patched game")
    raw = rsp.mem(base + TIMER_OFFSET, TIMER_SIZE)
    if len(raw) != TIMER_SIZE or not any(raw):
        raise ValueError("Timer function window is missing")
    words = struct.unpack("<" + "I" * (TIMER_SIZE // 4), raw)
    return {
        "build_id": build_id,
        "timer_function_main_offset": f"main+0x{TIMER_OFFSET:08x}",
        "window_first_main_offset": f"main+0x{TIMER_OFFSET:08x}",
        "instruction_words_u32_le": [f"0x{w:08x}" for w in words],
        "sha256_window": hashlib.sha256(raw).hexdigest(),
        "private": "Short excerpt of user's own game code; NEVER commit or publish this JSON.",
        "note": "Static function excerpt; code does not establish runtime timer semantics alone."
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", type=Path, required=True, help="Current launch eden_log.txt")
    p.add_argument("--port", type=int, default=6543)
    p.add_argument("--output", type=Path, default=Path("timer_source_window.json"))
    args = p.parse_args()
    if not 1 <= args.port <= 65535:
        p.error("Port must be 1..65535")
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        try:
            state = rsp.packet("?")
            if not state.startswith(("T", "S")):
                raise RuntimeError("Guest not at initial stopped debug state; restart emulator")
            base = detect_main_base(args.log.read_text(errors="replace"))
            report = capture_timer_source(rsp, base)
        finally:
            try:
                rsp.send_continue()
            except OSError:
                pass
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("Saved private timer function excerpt:", args.output)
    print("Guest resumed; do not commit JSON to GitHub.")


if __name__ == "__main__":
    main()
