#!/usr/bin/env python3
"""Verify E0F3 frame-step branch reachability from PRIVATE JSON code windows.

Source-only / read-only. The input JSON dumps contain original game code;
DO NOT commit them. Output is numeric/structural only, not instruction bytes.

A bounded direct-branch graph establishes reachability within the captured
excerpt under normal BL return semantics. This is not a proof of dynamic
callback behavior, other threads, or V9's runtime execution.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import struct

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
START, FIRST_BYTES = 0x006E6BE0, 0x400
CONT, SECOND_BYTES = 0x006E6FE0, 0x700
GATE = 0x006E6CC8
FIRST_CALL = 0x006E6DD8
SECOND_CALL = 0x006E70F8
CALLEE = 0x03B4E300
KEY_WORDS = {
    GATE: 0x37080289,
    0x006E6CF8: 0xB8290108,  # LDADD +1 first path
    FIRST_CALL: 0x94D19D4A,  # BL known timing-config converter
    0x006E6D24: 0xB8293108,  # bit5 LDSET
    0x006E6D48: 0xB8291108,  # bit5 LDCLR
    0x006E70C8: 0xB8290108,  # LDADD +1 second path
    SECOND_CALL: 0x94D19C82,
}


def sign_extend(value, bits):
    sign = 1 << (bits - 1)
    return value - (1 << bits) if value & sign else value


def branch_target(pc, opcode):
    if opcode & 0xFC000000 in (0x14000000, 0x94000000):
        return pc + 4 * sign_extend(opcode & 0x03FFFFFF, 26)
    if opcode & 0xFF000010 == 0x54000000:
        return pc + 4 * sign_extend((opcode >> 5) & 0x7FFFF, 19)
    if opcode & 0x7E000000 == 0x34000000:
        return pc + 4 * sign_extend((opcode >> 5) & 0x7FFFF, 19)
    if opcode & 0x7E000000 == 0x36000000:
        return pc + 4 * sign_extend((opcode >> 5) & 0x3FFF, 14)
    return None


def successors(pc, opcode):
    op = opcode & 0xFFFFFFFF
    if op & 0xFC000000 == 0x14000000:  # unconditional B
        return [branch_target(pc, op)]
    if (op & 0xFF000010 == 0x54000000 or
            op & 0x7E000000 in (0x34000000, 0x36000000)):
        return [pc + 4, branch_target(pc, op)]
    if op & 0xFFFFFC1F in (0xD65F0000, 0xD61F0000):
        return []  # RET or indirect BR: cannot follow locally
    return [pc + 4]  # BL returns to next instruction for this graph


def reachable(words, start, end):
    pending = deque([start])
    visited = set()
    while pending:
        pc = pending.popleft()
        if pc == end:
            return True
        if pc in visited or pc not in words:
            continue
        visited.add(pc)
        pending.extend(next_pc for next_pc in successors(pc, words[pc])
                       if next_pc in words and next_pc not in visited)
    return False


def checked_window(data, start, length):
    if data.get("build_id") != BUILD:
        raise ValueError("Unexpected build ID; only E0F3 is supported")
    if data.get("window_first_main_offset") != f"main+0x{start:08x}" and data.get(
            "first_main_offset") != f"main+0x{start:08x}":
        raise ValueError("Unexpected private window start offset")
    items = data.get("instruction_words_u32_le")
    if not isinstance(items, list) or len(items) != length // 4:
        raise ValueError("Unexpected private window length")
    raw = struct.pack(f"<{len(items)}I", *(int(x, 16) for x in items))
    if hashlib.sha256(raw).hexdigest() != data.get("sha256_window"):
        raise ValueError("Private code-window digest mismatch")
    return {start + i * 4: word for i, word in enumerate(struct.unpack(
        f"<{len(items)}I", raw))}


def analyze_words(words):
    for pc, required in KEY_WORDS.items():
        if words.get(pc) != required:
            raise ValueError(f"Original fingerprint mismatch at main+0x{pc:08x}")
    if branch_target(FIRST_CALL, KEY_WORDS[FIRST_CALL]) != CALLEE or (
            branch_target(SECOND_CALL, KEY_WORDS[SECOND_CALL]) != CALLEE):
        raise ValueError("Unexpected timing-config call target")
    gate_target = branch_target(GATE, KEY_WORDS[GATE])
    if gate_target != 0x006E6D18:
        raise ValueError("Unexpected original flag branch target")
    return {
        "build_id": BUILD,
        "frame_flags_bit_tested": 1,
        "gate_main_offset": f"main+0x{GATE:08x}",
        "bit1_clear_can_reach_first": reachable(words, GATE + 4, FIRST_CALL),
        "bit1_set_can_reach_second": reachable(words, gate_target, SECOND_CALL),
        "first_continuation_can_reach_second": reachable(
            words, FIRST_CALL + 4, SECOND_CALL),
        "second_continuation_can_reach_first": reachable(
            words, SECOND_CALL + 4, FIRST_CALL),
        "bit5_set_and_clear_fingerprints_verified": True,
        "scope": "Direct branches in bounded E0F3 private code, assuming normal return from BL; "
                 "not a runtime physics-call count or patched-game trace.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("first_window", type=Path, help="Private frame_step_window.json")
    p.add_argument("followup", type=Path, help="Private frame_step_followup.json")
    args = p.parse_args()
    first = json.loads(args.first_window.read_text(encoding="utf-8"))
    follow = json.loads(args.followup.read_text(encoding="utf-8"))
    regions = follow.get("regions", [])
    continuation = next((r for r in regions if
                         r.get("name") == "frame_step_function_continuation"), None)
    if continuation is None:
        p.error("Missing private frame-step continuation")
    continuation = {**continuation, "build_id": follow.get("build_id")}
    words = checked_window(first, START, FIRST_BYTES)
    words.update(checked_window(continuation, CONT, SECOND_BYTES))
    print(json.dumps(analyze_words(words), indent=2))
    print("No original code was written or published.")


if __name__ == "__main__":
    main()
