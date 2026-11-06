#!/usr/bin/env python3
"""Read-only original E0F3 frame-step instruction window (PRIVATE).

No game patches, breakpoints, or watchpoints. Verify the unmodified
frame-step hook and source fingerprints, capture 1024 bytes, then resume
the initially stopped guest. NEVER commit the resulting private JSON.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct

from guest_timer_probe import HOOKS, RSP, detect_main_base, verify_unmodified_hook

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
START = 0x006E6BE0
SIZE = 0x400
HOOK = HOOKS[BUILD]
ORIGINAL_INSTRUCTIONS = {
    0x006E6BE0: 0xD503237F,
    0x006E6BF8: 0xF9405408,
    0x006E6C04: 0xF9401115,
    0x006E6C98: 0xBD42CAA0,
    0x006E6CC0: 0x1E220C21,
    0x006E6CC4: 0x1E201828,
    0x006E6CC8: 0x37080289,
}


def capture_frame_step(rsp, base, build_id=BUILD):
    if build_id != BUILD:
        raise ValueError("Frame-step window only verified for E0F3")
    if not 0x10000 <= base <= 0xFFFFFFFFFF or base & 0xFFF:
        raise ValueError("Invalid current-session main module base")
    verify_unmodified_hook(rsp, base + HOOK)
    if SIZE > 4096 or SIZE % 4 or not START <= HOOK < START + SIZE:
        raise ValueError("Unsafe frame-step window specification")
    raw = rsp.mem(base + START, SIZE)
    if len(raw) != SIZE or not any(raw):
        raise ValueError("Missing frame-step instruction bytes")
    words = struct.unpack("<" + "I" * (SIZE // 4), raw)
    for at, expected in ORIGINAL_INSTRUCTIONS.items():
        if not START <= at < START + SIZE or words[(at - START) // 4] != expected:
            raise ValueError(f"Original instruction mismatch at main+0x{at:08x}")
    return {
        "build_id": BUILD,
        "function_entry_main_offset": f"main+0x{START:08x}",
        "window_first_main_offset": f"main+0x{START:08x}",
        "frame_step_divide_word_index": (HOOK - START) // 4,
        "instruction_words_u32_le": [f"0x{w:08x}" for w in words],
        "sha256_window": hashlib.sha256(raw).hexdigest(),
        "private": "Original game instructions; never commit or publish this JSON.",
        "note": "Static read-only excerpt; not a runtime frame-step call-count trace."
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True,
                        help="Current-launch Eglantine eden_log.txt")
    parser.add_argument("--port", type=int, default=6543)
    parser.add_argument("--output", type=Path, default=Path("frame_step_window.json"))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be 1..65535")
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        try:
            state = rsp.packet("?")
            if not state.startswith(("T", "S")):
                raise RuntimeError("Guest must be stopped at initial GDB attach")
            base = detect_main_base(args.log.read_text(errors="replace"))
            report = capture_frame_step(rsp, base)
        finally:
            try:
                rsp.send_continue()
            except OSError:
                pass
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Private frame-step window saved: {args.output}. Guest resumed.")
    print("Upload this JSON privately in chat; do not commit it to GitHub.")


if __name__ == "__main__":
    main()
