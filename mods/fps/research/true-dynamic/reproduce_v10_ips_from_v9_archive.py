#!/usr/bin/env python3
"""Reproduce the first E0F3 isolated-step V10 IPS from a private V9 archive.

This never modifies the known-working-in-user-testing V10 binary and
does not contain any proprietary original game instructions. It verifies
the exact tester-owned archived V9 ZIP and IPS SHA-256, all helper words
against independently authored ARM64 assembly, all trampoline targets,
and the two excluded controller patches. Outputs only a 209-byte IPS32.

This is a reproducibility tool; E0F3 user-reported 10..45 FPS gameplay
success is valuable but not formal verification of all engine states.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import zipfile

from real_elapsed_probe_builder import ASM, assemble, encode_b

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
OLD_ZIP_SHA256 = "061d7d2fccf0d657a64ffa8e4b1c789efa16c056810c359137b6593b5fd08178"
OLD_IPS_SHA256 = "207519e2fe0bb2895732b6d5f8e43fbf3d5f90af32f2df36650192438c02f847"
V10_IPS_SHA256 = "306e36cec3efc28a38df627ed38245fe29008855a85cfe4a249a7d8fb2fd1365"
HOOK = 0x006E6CC4
GUARD = 0x03B4EF90
PRESENT = 0x03B4F080
# First six, next six, final four independent instructions.
HELPER_SEGMENTS = ((0x006E1864, 6), (0x006E0F04, 6), (0x006F1804, 4))
BRANCH_TARGETS = {
    HOOK: HELPER_SEGMENTS[0][0],
    0x006E187C: HELPER_SEGMENTS[1][0],
    0x006E0F1C: HELPER_SEGMENTS[2][0],
    0x006F1814: HOOK + 4,
}
V9_CONTROLLER_OPCODES = {GUARD: 0xD503201F, PRESENT: 0x52800021}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parse_ips32(data):
    if not data.startswith(b"IPS32") or not data.endswith(b"EEOF"):
        raise ValueError("Invalid IPS32 header or terminator")
    p = 5
    records = {}
    stop = len(data) - 4
    while p < stop:
        if p + 6 > stop:
            raise ValueError("Truncated IPS32 record")
        at, n = struct.unpack_from(">IH", data, p)
        p += 6
        if at < 0x100 or n != 4 or p + n > stop:
            raise ValueError("Expected unambiguous four-byte main-relative IPS32 records")
        offset = at - 0x100
        if offset in records or offset & 3:
            raise ValueError("Duplicate or unaligned instruction offset")
        records[offset] = struct.unpack_from("<I", data, p)[0]
        p += 4
    if p != stop:
        raise ValueError("IPS32 contains trailing bytes or malformed records")
    return records


def serialize_ips32(records):
    blob = bytearray(b"IPS32")
    for offset, word in sorted(records.items()):
        if offset < 0 or offset > 0xFFFFFF00 or offset & 3:
            raise ValueError("Invalid IPS32 instruction offset")
        blob += struct.pack(">IH", offset + 0x100, 4)
        blob += struct.pack("<I", word)
    return bytes(blob) + b"EEOF"


def build_from_v9_ips(v9_ips, helper_words):
    if sha256(v9_ips) != OLD_IPS_SHA256:
        raise ValueError("Unexpected archived E0F3 V9 IPS SHA-256")
    records = parse_ips32(v9_ips)
    if len(helper_words) != len(ASM) or len(helper_words) != 16:
        raise ValueError("Incorrect independently assembled helper length")
    expected_sites = set(V9_CONTROLLER_OPCODES) | set(BRANCH_TARGETS)
    pos = 0
    for start, count in HELPER_SEGMENTS:
        expected_sites.update(start + 4 * i for i in range(count))
        for i in range(count):
            if records.get(start + 4 * i) != helper_words[pos]:
                raise ValueError(f"Helper opcode mismatch at main+0x{start+4*i:08x}")
            pos += 1
    if set(records) != expected_sites or len(records) != 22:
        raise ValueError("Unexpected V9 patch offset set or record count")
    for site, expected_word in V9_CONTROLLER_OPCODES.items():
        if records[site] != expected_word:
            raise ValueError(f"Unexpected V9 controller edit at main+0x{site:08x}")
    for src, dest in BRANCH_TARGETS.items():
        if records[src] != encode_b(src, dest):
            raise ValueError(f"Unexpected trampoline branch at main+0x{src:08x}")

    # Remove *only* V9's controller guard and forced present value.
    new_records = {offset: word for offset, word in records.items()
                   if offset not in V9_CONTROLLER_OPCODES}
    if len(new_records) != 20:
        raise ValueError("Unexpected isolated-step record count")
    v10_ips = serialize_ips32(new_records)
    if len(v10_ips) != 209 or sha256(v10_ips) != V10_IPS_SHA256:
        raise ValueError("Reproduced V10 IPS does not match user-tested artifact")
    return v10_ips


def reproduce_from_archive(input_zip, helper_words):
    raw = Path(input_zip).read_bytes()
    if sha256(raw) != OLD_ZIP_SHA256:
        raise ValueError("Wrong archived V9 ZIP SHA-256")
    with zipfile.ZipFile(input_zip) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archived V9 ZIP integrity failure")
        found = [name for name in archive.namelist()
                 if name.endswith(f"/exefs/{BUILD}.ips")]
        if len(found) != 1:
            raise ValueError("Expected exactly one archived E0F3 IPS")
        v9_ips = archive.read(found[0])
    return build_from_v9_ips(v9_ips, helper_words)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archived-v9", type=Path, required=True,
                   help="Private V9 experimental ZIP from user File Library")
    p.add_argument("--output-ips", type=Path, required=True,
                   help="Path to a NEW private 209-byte E0F3 IPS file")
    args = p.parse_args()
    if args.output_ips.exists():
        p.error("Refusing to overwrite an existing IPS")
    ips = reproduce_from_archive(args.archived_v9, assemble())
    args.output_ips.parent.mkdir(parents=True, exist_ok=True)
    with args.output_ips.open("xb") as f:
        f.write(ips)
    print(f"Reproduced E0F3 user-tested V10 IPS, SHA-256: {sha256(ips)}")
    print("Source-only reproduction complete. Do not publish Nintendo code.")


if __name__ == "__main__":
    main()
