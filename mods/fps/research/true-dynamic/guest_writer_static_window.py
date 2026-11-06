#!/usr/bin/env python3
"""Safely read a tiny original game-code excerpt around a verified timer writer.

A diagnostic, not a game patch. It connects to the localhost GDB stub while
the game is waiting at its initial debug halt, checks the verified original
frame-step instruction, reads a strictly bounded instruction window around
one observed write site, resumes the game and saves a PRIVATE JSON report.
No software breakpoints, watchpoints or game-memory writes are used.
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
BEFORE = 0x200
AFTER = 0x80


def capture_window(rsp, base, *, build_id=BUILD):
    """Return a small code snippet. No instructions are patched or executed."""
    if build_id != BUILD:
        raise ValueError("Writer site not established for this build ID")
    if not 0x10000 <= base <= 0xFFFFFFFFFF or base & 3:
        raise ValueError("Invalid current main-module base")
    verify_unmodified_hook(rsp, base + HOOKS[build_id])
    start_offset = WRITER_OFFSET - BEFORE
    size = BEFORE + AFTER
    if size > 4096 or (size & 3):
        raise ValueError("Invalid bounded code-window size")
    raw = rsp.mem(base + start_offset, size)
    if len(raw) != size or not any(raw):
        raise ValueError("Writer code window not mapped")
    words = struct.unpack("<" + "I" * (size // 4), raw)
    return {
        "build_id": build_id,
        "writer_site_main_offset": f"main+0x{WRITER_OFFSET:08x}",
        "window_first_main_offset": f"main+0x{start_offset:08x}",
        "writer_word_index": BEFORE // 4,
        "instruction_words_u32_le": [f"0x{word:08x}" for word in words],
        "sha256_window": hashlib.sha256(raw).hexdigest(),
        "private": "Short excerpt from user's own original game code; do not commit or publish.",
        "note": "Read-only instruction window. Writer PC from a live GDB watchpoint may be before/after the actual store."
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", required=True, type=Path,
                    help="Current-session eden_log.txt, not a log from a previous launch")
    ap.add_argument("--port", type=int, default=6543)
    ap.add_argument("--output", type=Path, default=Path("writer_opcode_window.json"))
    args = ap.parse_args()
    if not 1 <= args.port <= 65535:
        ap.error("Port must be 1..65535")
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        try:
            stopped = rsp.packet("?")
            if not stopped.startswith(("T", "S")):
                raise RuntimeError("Debugger did not report a stopped guest. Restart Eglantine with GDB Stub enabled.")
            base = detect_main_base(args.log.read_text(errors="replace"))
            report = capture_window(rsp, base)
        finally:
            # The debugger is paused at boot; always attempt to resume.
            try:
                rsp.send_continue()
            except OSError:
                pass
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2)
    print(f"Writer opcode window saved to {args.output}. The game was resumed.")
    print("Upload ONLY this JSON here privately; do not put game code on GitHub.")


if __name__ == "__main__":
    main()
