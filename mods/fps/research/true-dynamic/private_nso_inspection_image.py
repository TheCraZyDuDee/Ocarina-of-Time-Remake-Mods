#!/usr/bin/env python3
"""Create a PRIVATE, *inspection-only* NSO image from an original NSO.

No keys or copyrighted content are distributed, logged, uploaded or committed.
This tool does not emit a runnable NSO: its new segment layout is for the
repo's static module+0x100 opcode inspectors, not for game installation.

This tool does not bundle any proprietary or GPL decompression implementation.
For ZBIC modules (newer Switch firmware), install the independently licensed
'zbic' package in your private analysis environment.  For LZ4, install 'lz4'.
"""
import argparse
import hashlib
import importlib
from pathlib import Path
import struct

MAX_SEGMENT_SIZE = 256 * 1024 * 1024
NSO_HEADER_SIZE = 0x100
SEGMENT_NAMES = ("text", "rodata", "data")


def inspect_header(data: bytes) -> tuple[int, list[dict]]:
    if len(data) < NSO_HEADER_SIZE or data[:4] != b"NSO0":
        raise ValueError("Input must have an NSO0 header")
    flags = struct.unpack_from("<I", data, 0xC)[0]
    sections = []
    previous_end = NSO_HEADER_SIZE
    for index, name in enumerate(SEGMENT_NAMES):
        offset, memory_offset, expected_size = struct.unpack_from(
            "<III", data, 0x10 + 16 * index
        )
        packed_size = struct.unpack_from("<I", data, 0x60 + 4 * index)[0]
        compressed = bool(flags & (1 << index))
        source_size = packed_size if compressed else expected_size
        if (expected_size > MAX_SEGMENT_SIZE or source_size > MAX_SEGMENT_SIZE
                or source_size <= 0 or expected_size <= 0
                or offset < NSO_HEADER_SIZE or offset + source_size > len(data)):
            raise ValueError(f"Invalid {name} NSO descriptor")
        if offset < previous_end:
            raise ValueError("File segments overlap")
        previous_end = offset + source_size
        sections.append(dict(name=name, index=index, file_offset=offset,
                             memory_offset=memory_offset, compressed=compressed,
                             source_size=source_size, expected_size=expected_size))
    for a,b in zip(sections,sections[1:]):
        if a['memory_offset'] + a['expected_size'] > b['memory_offset']:
            raise ValueError('Virtual segments overlap')
    return flags, sections


def decode_section(raw: bytes, flags: int, section: dict) -> bytes:
    if not section["compressed"]:
        result = raw
    elif flags & 0x80:
        if not raw.startswith(b"ZBIC"):
            raise ValueError("ZBIC flag was set but segment does not start with ZBIC")
        try:
            zbic = importlib.import_module("zbic")
        except ImportError as exc:
            raise RuntimeError("ZBIC requires 'pip install zbic' in PRIVATE environment") from exc
        result = zbic.decompress(raw)
    else:
        try:
            lz4 = importlib.import_module("lz4.block")
        except ImportError as exc:
            raise RuntimeError("LZ4 requires 'pip install lz4' in PRIVATE environment") from exc
        result = lz4.decompress(raw, uncompressed_size=section["expected_size"])
    if len(result) != section["expected_size"]:
        raise ValueError(f"{section['name']} decompressed size mismatch")
    return result


def make_inspection_image(original: bytes) -> tuple[bytes, str]:
    flags, sections = inspect_header(original)
    build_id = original[0x40:0x54].hex().upper()
    if len(build_id) != 40:
        raise ValueError("Missing build ID")
    target_size = NSO_HEADER_SIZE + max(
        segment["memory_offset"] + segment["expected_size"] for segment in sections
    )
    if target_size > 768 * 1024 * 1024:
        raise ValueError("Combined NSO segments too large")
    image = bytearray(target_size)
    image[:NSO_HEADER_SIZE] = original[:NSO_HEADER_SIZE]
    for segment in sections:
        start = segment["file_offset"]
        raw = original[start:start + segment["source_size"]]
        unpacked = decode_section(raw, flags, segment)
        index = segment["index"]
        digest = hashlib.sha256(unpacked).digest()
        if digest != original[0xA0 + 32*index:0xC0 + 32*index]:
            raise ValueError(f"{segment['name']} SHA-256 mismatch")
        at = NSO_HEADER_SIZE + segment["memory_offset"]
        image[at:at+len(unpacked)] = unpacked
    return bytes(image), build_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_nso", type=Path)
    parser.add_argument("output_inspection_image", type=Path)
    args = parser.parse_args()
    if args.original_nso.resolve() == args.output_inspection_image.resolve():
        parser.error("Input and output paths must differ")
    if args.output_inspection_image.exists():
        parser.error("Refusing to overwrite an existing file")
    source = args.original_nso.read_bytes()
    flags, segments = inspect_header(source)
    print("Compression:", "ZBIC" if flags & 0x80 else "LZ4 or uncompressed")
    print("Segments:", ", ".join(x['name'] for x in segments))
    image, build_id = make_inspection_image(source)
    args.output_inspection_image.write_bytes(image)
    print("Verified 3 segment hashes. Build ID:", build_id)
    print("PRIVATE output:", args.output_inspection_image)
    print("Do NOT upload, commit or share the inspection image")


if __name__ == "__main__":
    main()
