#!/usr/bin/env python3
"""Validate PRIVATE inspection-only NSO layout using original NSO hashes.

Do not confuse this with Nintendo's runnable NSO file format. The companion
private_nso_inspection_image.py decodes compressed original segments into a
memory-offset layout at 0x100+mem_off, while retaining the original 0x100
header as provenance. The source-only experimental FPS builder expects
exactly this verified inspection layout; NEVER pass the original ZBIC blob
directly or change the still-compressed NSO header's file offsets.

No proprietary code or keys are bundled, printed, or distributed.
"""
import hashlib
from pathlib import Path
import struct

HEADER_BYTES = 0x100
MAX_SECTION = 256 * 1024 * 1024
MAX_INSPECTION = 768 * 1024 * 1024
SEGMENTS = ("text", "rodata", "data")


def validate_inspection_image(image: bytes, expected_build: str) -> list[dict]:
    if not isinstance(image, (bytes, bytearray, memoryview)):
        raise ValueError("Expected private inspection image bytes")
    if len(image) < HEADER_BYTES or image[:4] != b"NSO0":
        raise ValueError("Missing private NSO inspection image header")
    actual_build = bytes(image[0x40:0x54]).hex().upper()
    if actual_build != expected_build:
        raise ValueError("Original build ID mismatch")
    original_flags = struct.unpack_from("<I", image, 0xC)[0]
    # The unaltered original header has bit 7 set for ZBIC and all
    # three per-segment compressed bits set. This check is for E0F3.
    if original_flags & 0x87 != 0x87:
        raise ValueError("Expected original compressed-ZBIC NSO header provenance")
    expected_end = HEADER_BYTES
    previous_memory_end = 0
    report = []
    for index, name in enumerate(SEGMENTS):
        file_offset, memory_offset, uncompressed = struct.unpack_from(
            "<III", image, 0x10 + 16 * index)
        stored_size = struct.unpack_from("<I", image, 0x60 + 4 * index)[0]
        if not (0 < uncompressed <= MAX_SECTION and
                0 < stored_size <= MAX_SECTION and
                file_offset >= HEADER_BYTES and
                memory_offset >= previous_memory_end and
                (index != 0 or memory_offset == 0)):
            raise ValueError(f"Invalid {name} inspection image header descriptor")
        at = HEADER_BYTES + memory_offset
        end = at + uncompressed
        if end > MAX_INSPECTION or end > len(image):
            raise ValueError(f"Missing {name} decoded memory section")
        # The *file* offsets/packed sizes above describe original compressed
        # bytes and must NOT be used to locate unpacked inspection segments.
        digest = hashlib.sha256(memoryview(image)[at:end]).digest()
        if digest != bytes(image[0xA0 + 32 * index: 0xC0 + 32 * index]):
            raise ValueError(f"{name} decoded section SHA-256 mismatch")
        expected_end = max(expected_end, end)
        previous_memory_end = memory_offset + uncompressed
        report.append({"section": name, "memory_offset": memory_offset,
                       "uncompressed_size": uncompressed,
                       "sha256_verified": True})
    if len(image) != expected_end:
        raise ValueError("Private inspection image has unexpected trailing or missing bytes")
    return report


def load_verified_inspection_image(path: Path, expected_build: str) -> bytes:
    raw = Path(path).read_bytes()
    validate_inspection_image(raw, expected_build)
    return raw
