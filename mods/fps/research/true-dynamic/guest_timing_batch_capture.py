#!/usr/bin/env python3
"""ONE-SHOT E0F3 timing-source batch capture (private original code).

Captures three original-code routines in one GDB session: the now-resolved
timing callback, FPS setter and presentation setter. No game modifications,
breakpoints, code injection, timers or FPS claims. It must never upload or
commit its private JSON. Restrict use to the user's legally held game.

Run at initial Eglantine guest debugger stop (no save required). Requires
guest_timer_probe.py alongside this file. It resumes the guest on exit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct

from guest_timer_probe import HOOKS, RSP, detect_main_base, verify_unmodified_hook

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
TEXT_END = 0x03C461D0
CALLBACK = 0x02F52DF0
CALLBACK_PREFIX_SHA256 = "e138ddb9b69b7b8d9c8db9443980261995f0efe24586d0e11111bc24727f6a50"
ORIGINAL_CONTROLLER_CHECKS = {
    0x03B4EF90: 0x37000728,  # TBNZ on controller flag
    0x03B4F080: 0xB9404A81,  # LDR presentation interval from controller
    0x03B4F088: 0x97E4754E,  # BL native presentation setter
    0x03B4F190: 0x97E639D8,  # BL shared FPS setter (original audit)
}
TARGETS = (
    ("timing_callback", CALLBACK, 0x1000),
    ("presentation_setter", 0x0346C5C0, 0xA00),
    ("native_fps_setter", 0x004DC0F0, 0xA00),
)


def bl_target(offset, opcode):
    if (opcode & 0xFC000000) != 0x94000000:
        raise ValueError("Expected original AArch64 direct BL")
    immediate = opcode & 0x03FFFFFF
    if immediate & (1 << 25):
        immediate -= 1 << 26
    return offset + 4 * immediate


def preflight(rsp, base, build=BUILD):
    if build != BUILD:
        raise ValueError("Batch windows verified only for original E0F3 build")
    if not (0x10000 <= base < (1 << 40)) or (base & 0xFFF):
        raise ValueError("Invalid current-session main module base")
    verify_unmodified_hook(rsp, base + HOOKS[BUILD])
    for offset, word in ORIGINAL_CONTROLLER_CHECKS.items():
        if struct.unpack("<I", rsp.mem(base + offset, 4))[0] != word:
            raise ValueError(f"Unexpected original controller opcode at main+0x{offset:08x}")
    if bl_target(0x03B4F088, ORIGINAL_CONTROLLER_CHECKS[0x03B4F088]) != 0x0346C5C0:
        raise ValueError("Native presentation call target changed")
    if bl_target(0x03B4F190, ORIGINAL_CONTROLLER_CHECKS[0x03B4F190]) != 0x004DC0F0:
        raise ValueError("Native FPS setter call target changed")
    prefix = rsp.mem(base + CALLBACK, 128)
    if hashlib.sha256(prefix).hexdigest() != CALLBACK_PREFIX_SHA256:
        raise ValueError("Callback prefix differs from verified original gameplay capture")
    return prefix


def capture(rsp, base, build=BUILD):
    prefix = preflight(rsp, base, build)
    regions = []
    for label, offset, count in TARGETS:
        if offset & 3 or count & 3 or count > 4096 or offset + count > TEXT_END:
            raise ValueError(f"Unsafe bounded source range for {label}")
        raw = rsp.mem(base + offset, count)
        if len(raw) != count or raw == bytes(count):
            raise ValueError(f"Missing expected original code for {label}")
        if label == "timing_callback" and raw[:128] != prefix:
            raise ValueError("Callback changed between fingerprint and code read")
        unpacked = struct.unpack(f"<{count // 4}I", raw)
        regions.append({
            "name": label,
            "start_main_offset": f"main+0x{offset:08x}",
            "length_bytes": count,
            "sha256_window": hashlib.sha256(raw).hexdigest(),
            "instruction_words_u32_le": [f"0x{w:08x}" for w in unpacked],
        })
    return {
        "build_id": BUILD,
        "regions": regions,
        "private": "Contains original copyrighted game instructions; never commit or publish.",
        "note": "Static source capture; does not prove callback execution rate or V9 gameplay behavior.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", type=Path, required=True, help="Current-session Eglantine eden_log.txt")
    p.add_argument("--port", type=int, default=6543)
    p.add_argument("--output", type=Path, default=Path("timing_batch_private.json"))
    args = p.parse_args()
    if not (1 <= args.port <= 65535):
        p.error("Port must be 1..65535")
    if args.output.exists():
        p.error("Output already exists; use a fresh path to prevent overwriting")
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        try:
            stop = rsp.packet("?")
            if not stop.startswith(("T", "S")):
                raise RuntimeError("Guest must start at initial GDB halt")
            base = detect_main_base(args.log.read_text(errors="replace"))
            result = capture(rsp, base)
        finally:
            try:
                rsp.send_continue()
            except OSError:
                pass
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2)
    print(f"Saved one PRIVATE batch file: {args.output}. Game resumed.")
    print("Never commit original instructions or a game dump to GitHub.")


if __name__ == "__main__":
    main()
