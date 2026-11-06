#!/usr/bin/env python3
"""Verify original frame-step dataflow fingerprints for both supported OoT NSOs.

Read only. Returns a small JSON manifest of instruction identities and structural
relationships; intentionally never prints or exports proprietary executable bytes.

This tool does *not* establish runtime values or that the update path executes on
all frames. It is a gate for further reverse engineering, not a playable mod.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

# Module-relative offsets and exact original AArch64 instruction words.
# Structural fingerprints only, not a copy of the game's executable.
SITES = {
    "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348": {
        "frame_step_function_entry": (0x006E6BE0, 0xD503237F),
        "manager_pointer_at_context_a8": (0x006E6BF8, 0xF9405408),
        "fps_state_from_manager_20": (0x006E6C04, 0xF9401115),
        "float_load_near_state_2c8_unverified": (0x006E6C98, 0xBD42CAA0),
        "base_rate_60_or_30": (0x006E6CC0, 0x1E220C21),
        "sim_step_divide": (0x006E6CC4, 0x1E201828),
        "first_instruction_after_hook": (0x006E6CC8, 0x37080289),
        "interval_controller_samples": (0x03B4EFA0, 0xA954D668),
        "fps_target_controller_samples": (0x004DBE80, 0xA954D688),
    },
    "33FA6C2C23848282A77E8B88A0A93F4887C55920": {
        "manager_pointer_at_context_a8": (0x006B5920, 0xF9405408),
        "fps_state_from_manager_20": (0x006B592C, 0xF9401115),
        "float_load_near_state_2c8_unverified": (0x006B59C8, 0xBD42CAA0),
        "base_rate_60_or_30": (0x006B5A04, 0x1E220C21),
        "sim_step_divide": (0x006B5A08, 0x1E201828),
        "first_instruction_after_hook": (0x006B5A0C, 0x37080289),
        "interval_controller_samples": (0x03AF1930, 0xA954D668),
        "fps_target_controller_samples": (0x0045DAF0, 0xA954D688),
    },
}


def u32(data: bytes, module_offset: int) -> int:
    at = 0x100 + module_offset
    if at < 0x100 or at + 4 > len(data):
        raise ValueError("instruction outside file")
    return struct.unpack_from("<I", data, at)[0]


def original_nso_build_id(data: bytes) -> str:
    if len(data) < 0x100 or data[:4] != b"NSO0":
        raise ValueError("missing NSO header")
    build_id = data[0x40:0x54].hex().upper()
    if build_id not in SITES:
        raise ValueError("unsupported build ID")
    for i in range(3):
        _, start, length = struct.unpack_from("<III", data, 0x10 + 16 * i)
        first = 0x100 + start
        if first + length > len(data):
            raise ValueError("truncated or compressed NSO segment")
        want = data[0xA0 + 32 * i : 0xC0 + 32 * i]
        if hashlib.sha256(memoryview(data)[first : first + length]).digest() != want:
            raise ValueError("segment digest mismatch: use original decompressed NSO")
    return build_id


def inspect(data: bytes) -> dict:
    build_id = original_nso_build_id(data)
    checks = {
        label: {
            "location": f"main+0x{offset:08X}",
            "original_word_matches": u32(data, offset) == expected,
        }
        for label, (offset, expected) in SITES[build_id].items()
    }
    return {
        "build_id": build_id,
        "all_original_words_match": all(x["original_word_matches"] for x in checks.values()),
        "instruction_fingerprints": checks,
        "verified_static_expression": "fdiv s8,s1,s0; nearby code has a float load from x21+0x2c8, but live s0 provenance is NOT verified",
        "v9_unverified_assumption": "FPS state+0x100 contains latest elapsed frame ticks",
        "runtime_timer_units_verified": False,
        "per_frame_update_frequency_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decompressed_original_nso", type=Path)
    args = parser.parse_args()
    result = inspect(args.decompressed_original_nso.read_bytes())
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["all_original_words_match"]:
        parser.exit(1, "Opcode mismatch: do not generate a timing patch\n")


if __name__ == "__main__":
    main()
