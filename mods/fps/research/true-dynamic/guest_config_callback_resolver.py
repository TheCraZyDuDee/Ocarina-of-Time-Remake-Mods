#!/usr/bin/env python3
"""Read-only E0F3 timing-config callback pointer resolver (research only).

The private original callee at main+0x03B4E300 checks config+0x1C8
before calling a virtual method at callback-vtable+0x10. This script
does NOT invoke it. It checks exact original opcode fingerprints, then
reads only its pointer chain after gameplay is loaded. If the method
lies inside the verified E0F3 main TEXT range, it optionally captures
128 bytes of original code. Raw private output must NEVER be committed.

No breakpoints, watchpoints, instruction changes, IPS mods or game
memory writes. Guest must start at its initial GDB stop, then run until
you press Enter after reaching stable gameplay.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct

from guest_timer_probe import HOOKS, RSP, detect_main_base, verify_unmodified_hook

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
GLOBAL_HOLDER_SLOT = 0x04C7E890
MAIN_TEXT_SIZE = 0x03C461D0  # E0F3 original NSO text virtual size
CONFIG_CALLBACK_FIELD = 0x1C8
VTABLE_METHOD_OFFSET = 0x10
CODE_SIZE = 128
CALLEE_CHECKS = {
    0x03B4E364: 0xF940E660,  # ldr x0,[x19,#0x1c8]
    0x03B4E368: 0xB9001E68,  # str w8,[x19,#0x1c]
    0x03B4E36C: 0xB40000A0,  # cbz x0,...
    0x03B4E370: 0xF9400008,  # ldr x8,[x0]
    0x03B4E374: 0xAA1303E1,  # mov x1,x19
    0x03B4E378: 0xF9400908,  # ldr x8,[x8,#0x10]
    0x03B4E37C: 0xD63F0100,  # blr x8
}


def valid_pointer(value, *, executable=False):
    return (0x10000 <= value < (1 << 48)
            and not (value & (3 if executable else 7)))


def u64(rsp, address):
    return struct.unpack("<Q", rsp.mem(address, 8))[0]


def resolve_callback(rsp, main_base, build_id=BUILD):
    if build_id != BUILD:
        raise ValueError("Callback site verified only for E0F3 build")
    if not valid_pointer(main_base) or main_base & 0xFFF:
        raise ValueError("Invalid main module base")
    verify_unmodified_hook(rsp, main_base + HOOKS[BUILD])
    for site, expected in CALLEE_CHECKS.items():
        observed = struct.unpack("<I", rsp.mem(main_base + site, 4))[0]
        if observed != expected:
            raise ValueError(f"Original callback fingerprint mismatch at main+0x{site:08x}")

    holder = u64(rsp, main_base + GLOBAL_HOLDER_SLOT)
    if not valid_pointer(holder):
        raise RuntimeError("Timing-config global holder is absent or invalid")
    config = u64(rsp, holder)
    if not valid_pointer(config):
        raise RuntimeError("Timing config is absent or invalid")
    step = struct.unpack("<f", rsp.mem(config + 0x10, 4))[0]
    nominal = struct.unpack("<I", rsp.mem(config + 0x1C, 4))[0]
    callback = u64(rsp, config + CONFIG_CALLBACK_FIELD)
    result = {
        "build_id": BUILD,
        "checked_original_callback_fingerprints": True,
        "config_step": step,
        "config_nominal_rate": nominal,
        "callback_object_present": bool(callback),
        "private": "Private runtime pointer evidence; never commit code or raw guest addresses.",
        "note": "Presence/method pointer alone does not prove that callback changes FPS or runs in gameplay.",
    }
    if not callback:
        return result
    if not valid_pointer(callback):
        raise RuntimeError("Callback object pointer invalid")
    vtable = u64(rsp, callback)
    if not valid_pointer(vtable):
        raise RuntimeError("Callback virtual table pointer invalid")
    method = u64(rsp, vtable + VTABLE_METHOD_OFFSET)
    if not valid_pointer(method, executable=True):
        raise RuntimeError("Callback method pointer invalid")
    in_main = main_base <= method and method + CODE_SIZE <= main_base + MAIN_TEXT_SIZE
    result["callback_method_guest_address"] = f"0x{method:x}"
    result["callback_method_location"] = (
        f"main+0x{method - main_base:08x}" if in_main else "outside_verified_main_text")
    if in_main:
        raw = rsp.mem(method, CODE_SIZE)
        if len(raw) != CODE_SIZE:
            raise RuntimeError("Incomplete bounded callback code window")
        result["instruction_words_u32_le"] = [
            f"0x{x:08x}" for x in struct.unpack("<32I", raw)
        ]
        result["sha256_window"] = hashlib.sha256(raw).hexdigest()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", type=Path, required=True, help="Current launch Eglantine eden_log.txt")
    p.add_argument("--port", type=int, default=6543)
    p.add_argument("--output", type=Path, default=Path("config_callback_target.json"))
    args = p.parse_args()
    if not 1 <= args.port <= 65535:
        p.error("Port must be 1..65535")
    with socket.create_connection(("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        try:
            stopped = rsp.packet("?")
            if not stopped.startswith(("T", "S")):
                raise RuntimeError("Guest is not at its initial stopped debugger state")
            print("Load stable gameplay, then press Enter in the terminal.", flush=True)
            rsp.send_continue()
            input()
            sock.sendall(b"\x03")
            stopped = rsp.recv_packet()
            if not stopped.startswith(("T", "S")):
                raise RuntimeError("Unexpected result from manual gameplay interrupt")
            base = detect_main_base(args.log.read_text(errors="replace"))
            report = resolve_callback(rsp, base)
        finally:
            try:
                rsp.send_continue()
            except OSError:
                pass
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Saved private callback report: {args.output}. Guest resumed.")
    print("Upload ONLY privately in chat. Never publish original-code windows.")


if __name__ == "__main__":
    main()
