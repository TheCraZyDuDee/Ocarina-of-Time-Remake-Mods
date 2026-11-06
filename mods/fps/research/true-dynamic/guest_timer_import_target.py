#!/usr/bin/env python3
"""Private, read-only inspection of the resolved E0F3 timer import target.

Use only with your own unmodified game and a compatible local Eglantine GDB
stub. Pauses once after the scene loads, reads one verified import pointer
and up to 256 bytes at its target, resumes the game, and writes a PRIVATE JSON.
No game memory writes, patches, breakpoints or emulator source dependencies.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct

from guest_timer_probe import HOOKS, RSP, detect_main_base, verify_unmodified_hook

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
STUB_MAIN_OFFSET = 0x03C41FD0
EXPECTED_GOT_MAIN_OFFSET = 0x04CBF1B0
WRITER_MAIN_OFFSET = 0x0346C7EC
WRITER_WORD = 0xF9008268  # Tiny opcode identity check, not a code dump.
TARGET_CAPTURE_BYTES = 0x100
MAIN_MAX_SIZE = 0x04EA0000  # Known E0F3 mapping size from prior tester log.


def decode_plt_import_slot(words, stub_guest_pc):
    """Validate a standard AArch64 PLT stub and compute its pointer slot."""
    if len(words) != 4:
        raise ValueError("Expected exactly four PLT words")
    adrp, ldr, add, br = words
    # adrp x16; ldr x17,[x16,#imm*8]; add x16,x16,#imm; br x17
    if ((adrp & 0x9F00001F) != 0x90000010 or
            (ldr & 0xFFC003FF) != 0xF9400211 or
            (add & 0xFFC003FF) != 0x91000210 or
            br != 0xD61F0220):
        raise ValueError("Unexpected timer-import trampoline opcode shape")
    ldr_disp = ((ldr >> 10) & 0xFFF) * 8
    add_disp = (add >> 10) & 0xFFF
    if ((add >> 22) & 3) or ldr_disp != add_disp:
        raise ValueError("Trampoline has inconsistent pointer slot offsets")
    imm21 = (((adrp >> 5) & 0x7FFFF) << 2) | ((adrp >> 29) & 3)
    if imm21 & (1 << 20):
        imm21 -= 1 << 21
    return (stub_guest_pc & ~0xFFF) + (imm21 << 12) + ldr_disp


def capture_import_target(rsp, main_base):
    """Read-only: fail closed before dereferencing any dynamic pointer."""
    if main_base < 0x10000 or main_base >= 0xFFFFFFFFFF or main_base & 0xFFF:
        raise ValueError("Invalid current main base")
    verify_unmodified_hook(rsp, main_base + HOOKS[BUILD])
    writer_word = struct.unpack('<I', rsp.mem(main_base + WRITER_MAIN_OFFSET, 4))[0]
    if writer_word != WRITER_WORD:
        raise ValueError("Timer writer opcode mismatch; stop before dereferencing import")
    stub = rsp.mem(main_base + STUB_MAIN_OFFSET, 16)
    if len(stub) != 16:
        raise ValueError("Timer import trampoline was not readable")
    slot = decode_plt_import_slot(struct.unpack('<4I', stub), main_base + STUB_MAIN_OFFSET)
    if slot != main_base + EXPECTED_GOT_MAIN_OFFSET:
        raise ValueError("Unexpected import slot; incorrect build or load base")
    target = struct.unpack('<Q', rsp.mem(slot, 8))[0]
    result = {
        "build_id": BUILD,
        "import_stub_main_offset": f"main+0x{STUB_MAIN_OFFSET:08x}",
        "import_pointer_slot_main_offset": f"main+0x{EXPECTED_GOT_MAIN_OFFSET:08x}",
        "resolved_target_guest_address": f"0x{target:x}",
        "resolved_target_location": (f"main+0x{target - main_base:08x}"
                                     if main_base <= target < main_base + MAIN_MAX_SIZE
                                     else "outside_main_module"),
        "private": "Contains addresses and a short excerpt of private game code. Never commit this JSON.",
    }
    if target < 0x10000 or target >= (1 << 48) or target & 3 or target == slot:
        result["target_code_status"] = "not_read_invalid_or_unresolved_pointer"
        return result
    try:
        raw = rsp.mem(target, TARGET_CAPTURE_BYTES)
        if len(raw) != TARGET_CAPTURE_BYTES or not any(raw):
            raise ValueError("Target code missing or zeroed")
    except (ValueError, OSError, socket.timeout, ConnectionError) as exc:
        result["target_code_status"] = "not_readable"
        result["read_error_type"] = type(exc).__name__
        return result
    result.update({
        "target_code_status": "captured",
        "target_window_first_guest_address": f"0x{target:x}",
        "instruction_words_u32_le": [f"0x{v:08x}" for v in struct.unpack('<64I', raw)],
        "sha256_window": hashlib.sha256(raw).hexdigest(),
    })
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--log', required=True, type=Path,
                    help='Current Eglantine launch eden_log.txt; never reuse old log')
    ap.add_argument('--port', type=int, default=6543)
    ap.add_argument('--output', type=Path, default=Path('timer_import_target.json'))
    ap.add_argument('--immediate', action='store_true',
                    help='Inspect initial debugger halt instead of running to menu/gameplay')
    args = ap.parse_args()
    if not 1 <= args.port <= 65535:
        ap.error('Port must be 1..65535')
    with socket.create_connection(('127.0.0.1', args.port), timeout=10) as sock:
        sock.settimeout(30)
        rsp = RSP(sock)
        try:
            initial = rsp.packet('?')
            if not initial.startswith(('T', 'S')):
                raise RuntimeError('Guest is not at initial debugger halt; restart Eglantine')
            if not args.immediate:
                print('Connected. Guest will run. Navigate to menu or gameplay, then press Enter here.', flush=True)
                rsp.send_continue()
                input()
                sock.sendall(b'\x03')  # Remote interrupt, no guest memory write.
                stop = rsp.recv_packet()
                if not stop.startswith(('T', 'S')):
                    raise RuntimeError('Guest did not confirm debugger interrupt')
            main_base = detect_main_base(args.log.read_text(errors='replace'))
            report = capture_import_target(rsp, main_base)
        finally:
            try:
                rsp.send_continue()
            except OSError:
                pass
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print('Private resolved timer-import report:', args.output)
    print('Status:', report['target_code_status'], '; guest resumed.')
    print('Upload the JSON privately here, never to the public repository.')


if __name__ == '__main__':
    main()
