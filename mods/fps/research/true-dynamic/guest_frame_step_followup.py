#!/usr/bin/env python3
"""Bounded, read-only follow-up inspection of E0F3's frame-step consumers.

First original gameplay capture confirmed:
  - s8 accumulates (as double) at frame_context+0xD58 on one path
  - s8 is passed as s0 into main+0x03B4E300 on another path.
Read original code at the callee and continuation of the calling function.
No FPS mod, injected code, software breakpoints, watchpoints or game writes.
PRIVATE JSON contains copyrighted game instruction words: never commit it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct

from guest_timer_probe import HOOKS, RSP, detect_main_base, verify_unmodified_hook

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
CALL_SITE = 0x006E6DD8
CALLEE = 0x03B4E300
WINDOWS = (
    ("simulation_step_consumer_callee", CALLEE, 0x600),
    ("frame_step_function_continuation", 0x006E6FE0, 0x700),
)
# Newly verified identifiers, not copyrighted code excerpts.
ORIGINAL_CHECKS = {
    0x006E6CA8: 0x5E21D800,  # scvtf s0,s0: integer target FPS converted to float
    0x006E6D08: 0x1E22C101,  # fcvt d1,s8
    0x006E6D0C: 0x1E612800,  # fadd d0,d0,d1
    0x006E6DCC: 0x1E204100,  # fmov s0,s8
    CALL_SITE: 0x94D19D4A,  # bl main+0x03B4E300
}


def decode_bl_target(src_offset, word):
    if word & 0xFC000000 != 0x94000000:
        raise ValueError("Expected AArch64 BL instruction")
    rel = word & 0x03FFFFFF
    if rel & (1 << 25):
        rel -= 1 << 26
    return src_offset + rel * 4


def capture_followup(rsp, base, build_id=BUILD):
    if build_id != BUILD:
        raise ValueError("Follow-up source locations verified only for E0F3")
    if not 0x10000 <= base <= 0xFFFFFFFFFF or base & 0xFFF:
        raise ValueError("Invalid current-session main module base")
    verify_unmodified_hook(rsp, base + HOOKS[build_id])
    if decode_bl_target(CALL_SITE, ORIGINAL_CHECKS[CALL_SITE]) != CALLEE:
        raise ValueError("Static function-call offset inconsistency")
    for offset, expected in ORIGINAL_CHECKS.items():
        observed = struct.unpack("<I", rsp.mem(base + offset, 4))[0]
        if observed != expected:
            raise ValueError(f"Original opcode mismatch at main+0x{offset:08x}; no code window captured")
    regions = []
    for name, start, size in WINDOWS:
        if size > 4096 or size & 3 or start & 3:
            raise ValueError("Unsafe bounded instruction-window specification")
        raw = rsp.mem(base + start, size)
        if len(raw) != size or not any(raw):
            raise ValueError(f"Unmapped or empty original code at main+0x{start:08x}")
        words = struct.unpack("<" + "I" * (size // 4), raw)
        regions.append({
            "name": name,
            "first_main_offset": f"main+0x{start:08x}",
            "instruction_words_u32_le": [f"0x{w:08x}" for w in words],
            "sha256_window": hashlib.sha256(raw).hexdigest(),
        })
    return {
        "build_id": build_id,
        "call_site_main_offset": f"main+0x{CALL_SITE:08x}",
        "verified_direct_callee_main_offset": f"main+0x{CALLEE:08x}",
        "regions": regions,
        "private": "Contains original game code excerpts; never commit or publish.",
        "note": "Static disassembly follow-up; cannot prove per-present call frequency or whole-engine simulation correctness."
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, type=Path, help="Current-session eden_log.txt")
    parser.add_argument("--port", type=int, default=6543)
    parser.add_argument("--output", type=Path, default=Path("frame_step_followup.json"))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be 1..65535")
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        try:
            if not rsp.packet("?").startswith(("T", "S")):
                raise RuntimeError("Guest not initially stopped; restart Eglantine with GDB stub")
            base = detect_main_base(args.log.read_text(errors="replace"))
            report = capture_followup(rsp, base)
        finally:
            try:
                rsp.send_continue()
            except OSError:
                pass
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Saved private code follow-up: {args.output}. Guest resumed.")
    print("Upload JSON privately in chat; do NOT commit it to GitHub.")


if __name__ == "__main__":
    main()
