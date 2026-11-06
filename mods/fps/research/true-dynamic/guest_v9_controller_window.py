#!/usr/bin/env python3
"""Read-only original E0F3 V9 guard/presentation controller code capture.

No patch, no guest-code modifications, no GDB breakpoints. This checks the
original E0F3 instruction fingerprints at the 60Hz-guard and presentation
argument before reading a bounded 2048-byte contiguous original code
excerpt. The private output contains copyrighted game code. NEVER commit it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct

from guest_timer_probe import HOOKS, RSP, detect_main_base, verify_unmodified_hook

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
START = 0x03B4EE80
SIZE = 0x800
GUARD = 0x03B4EF90
PRESENT = 0x03B4F080
CHECKS = {
    GUARD: 0x37000728,   # TBNZ W8,#0,target; V9 incorrectly replaced with NOP
    PRESENT: 0xB9404A81, # LDR W1,[X20,#0x48]; V9 forced W1=1
}


def decode_tbnz_target(site, word):
    if word & 0x7E000000 != 0x36000000:
        raise ValueError("Expected TBNZ/TBZ instruction")
    off = (word >> 5) & 0x3FFF
    if off & 0x2000:
        off -= 0x4000
    return site + off * 4


def capture(rsp, base, build=BUILD):
    if build != BUILD:
        raise ValueError("Controller window only verified for E0F3 build")
    if base < 0x10000 or base >= 1 << 40 or base & 0xFFF:
        raise ValueError("Invalid current-session main module base")
    verify_unmodified_hook(rsp, base + HOOKS[BUILD])
    if not (START <= GUARD < START + SIZE and START <= PRESENT < START + SIZE):
        raise ValueError("Unsafe window specification")
    for offset, expected in CHECKS.items():
        raw = rsp.mem(base + offset, 4)
        if len(raw) != 4 or struct.unpack("<I", raw)[0] != expected:
            raise ValueError(f"Original source fingerprint mismatch at main+0x{offset:08x}")
    raw = rsp.mem(base + START, SIZE)
    if len(raw) != SIZE:
        raise RuntimeError("Incomplete original-code window")
    words = struct.unpack(f"<{SIZE // 4}I", raw)
    for offset, expected in CHECKS.items():
        if words[(offset - START) // 4] != expected:
            raise ValueError(f"Post-read fingerprint mismatch main+0x{offset:08x}")
    return {
        "build_id": BUILD,
        "first_main_offset": f"main+0x{START:08x}",
        "guard_main_offset": f"main+0x{GUARD:08x}",
        "guard_original_branch_target": f"main+0x{decode_tbnz_target(GUARD, CHECKS[GUARD]):08x}",
        "presentation_argument_load_offset": f"main+0x{PRESENT:08x}",
        "instruction_words_u32_le": [f"0x{word:08x}" for word in words],
        "sha256_window": hashlib.sha256(raw).hexdigest(),
        "private": "Original game code. Do not commit, publish or share except privately for analysis.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", type=Path, required=True,
                   help="Current-session Eglantine eden_log.txt")
    p.add_argument("--port", type=int, default=6543)
    p.add_argument("--output", type=Path, default=Path("v9_controller_original.json"))
    args = p.parse_args()
    if not 1 <= args.port <= 65535:
        p.error("Port must be 1..65535")
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        try:
            stopped = rsp.packet("?")
            if not stopped.startswith(("T", "S")):
                raise RuntimeError("Game must be at its initial GDB stop")
            base = detect_main_base(args.log.read_text(errors="replace"))
            result = capture(rsp, base)
        finally:
            try:
                rsp.send_continue()
            except OSError:
                pass
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2)
    print(f"Saved PRIVATE controller code: {args.output}; guest resumed.")


if __name__ == "__main__":
    main()
