#!/usr/bin/env python3
"""Read-only verifier for private, decompressed Ocarina main NSOs.

Reports only build identity, segment checksum results and known controller
instruction matches; produces no IPS, ZIP, code dump or game executable.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

SITES = {
    "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348": {
        "forced_mode_guard": (0x3B4EF90, 0x37000728),
        "measured_frame_to_int": (0x3B4EFF0, 0x1E380009),
        "adaptive_interval_selection": (0x3B4F004, 0x1A89B10A),
        "target_rate_from_interval": (0x3B4F05C, 0x1AD50D01),
        "present_interval_argument": (0x3B4F080, 0xB9404A81),
        "force_interval_initialization": (0x3B4F370, 0x52800788),
    },
    "33FA6C2C23848282A77E8B88A0A93F4887C55920": {
        "forced_mode_guard": (0x3AF1920, 0x37000728),
        "measured_frame_to_int": (0x3AF1980, 0x1E380009),
        "adaptive_interval_selection": (0x3AF1994, 0x1A89B10A),
        "target_rate_from_interval": (0x3AF19EC, 0x1AD50D01),
        "present_interval_argument": (0x3AF1A10, 0xB9404A81),
        "force_interval_initialization": (0x3AF1D00, 0x52800788),
    },
}
NSO_HEADER_BYTES = 0x100


def inspect(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < NSO_HEADER_BYTES or data[:4] != b"NSO0":
        raise ValueError("not an NSO header")
    build_id = data[0x40:0x54].hex().upper()
    if build_id not in SITES:
        raise ValueError(f"unsupported build ID: {build_id}")
    for index in range(3):
        _, memory_offset, length = struct.unpack_from("<III", data, 0x10 + index * 16)
        start, end = NSO_HEADER_BYTES + memory_offset, NSO_HEADER_BYTES + memory_offset + length
        if end > len(data):
            raise ValueError("compressed/truncated segment: use decompressed NSO")
        expected = data[0xA0 + 32 * index : 0xC0 + 32 * index]
        if hashlib.sha256(data[start:end]).digest() != expected:
            raise ValueError("segment hash mismatch (compressed or modified NSO)")
    sites = {}
    for label, (offset, expected) in SITES[build_id].items():
        at = NSO_HEADER_BYTES + offset
        if at + 4 > len(data):
            raise ValueError(f"truncated instruction at main+0x{offset:X}")
        actual = struct.unpack_from("<I", data, at)[0]
        sites[label] = {
            "module_offset": f"0x{offset:08X}",
            "expected_opcode": f"0x{expected:08X}",
            "matches_original": actual == expected,
        }
    return {
        "build_id": build_id,
        "verified_segment_hashes": 3,
        "sites": sites,
        "original_controller_intact": all(x["matches_original"] for x in sites.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decompressed_nso", type=Path)
    args = parser.parse_args()
    result = inspect(args.decompressed_nso)
    print(json.dumps(result, indent=2))
    if not result["original_controller_intact"]:
        raise SystemExit("Opcode mismatch; do not build or apply timing patches")


if __name__ == "__main__":
    main()
