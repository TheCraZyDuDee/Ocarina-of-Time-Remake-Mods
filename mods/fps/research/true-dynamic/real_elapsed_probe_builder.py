#!/usr/bin/env python3
"""V9 source-only diagnostic: elapsed-time frame-step scaling for OoT Switch 2.

NOT A COMPLETED DYNAMIC FPS MOD. Uses original user-provided decompressed
NSOs for read-only source validation; generates a small IPS32 patch ZIP
locally. Never package or commit game dumps or experimental ZIPs.

At the game's per-render simulation multiplier, replaces its assumption
of 60-or-30 ticks per nominal target frame with:
    delta = clamp( (60-or-30) * last_frame_ticks / CNTFRQ_EL0, 0.5, 4.0 )
This is intended only to test approximately 15-60 FPS without runaway
large steps after scene loading. At less than 15 FPS it can still slow.
"""
import argparse
import hashlib
import re
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

TITLE = "0400486024DEC000"
MOD = "V9 Real Elapsed Time Probe (Experimental)"
BUILDS = {
    "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348": {
        "guard": 0x3B4EF90,
        "present": 0x3B4F080,
        "delta_hook": 0x6E6CC4,
    },
    "33FA6C2C23848282A77E8B88A0A93F4887C55920": {
        "guard": 0x3AF1920,
        "present": 0x3AF1A10,
        "delta_hook": 0x6B5A08,
    },
}
# Independently authored AArch64 instructions. No emulator or game source
# copied. Preserve x8, d0; do not change live x9, x10, x19, NZCV or LR.
ASM = [
    "str x8, [sp, #-16]!",
    "str d0, [sp, #-16]!",
    "ldr x8, [x19, #0xa8]",
    "ldr x8, [x8, #0x20]",
    "ldr x8, [x8, #0x100]",
    "scvtf s8, x8",
    "mrs x8, cntfrq_el0",
    "scvtf s0, x8",
    "fmul s8, s8, s1",
    "fdiv s8, s8, s0",
    "fmov s0, #0.5",
    "fmaxnm s8, s8, s0",
    "fmov s0, #4.0",
    "fminnm s8, s8, s0",
    "ldr d0, [sp], #16",
    "ldr x8, [sp], #16",
]
EXPECTED = {"guard": 0x37000728, "present": 0xB9404A81, "delta_hook": 0x1E201828}


def encode_b(src: int, dst: int) -> int:
    diff = dst - src
    if diff % 4 or not -(1 << 27) <= diff < 1 << 27:
        raise ValueError("AArch64 B out of range")
    return 0x14000000 | ((diff // 4) & 0x3FFFFFF)


def decode_b(src: int, instruction: int) -> int:
    if instruction & 0xFC000000 != 0x14000000:
        raise ValueError("not an AArch64 B")
    diff = instruction & 0x3FFFFFF
    if diff & (1 << 25):
        diff -= 1 << 26
    return src + 4 * diff


def assemble() -> tuple[int, ...]:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "probe.s").write_text(".text\n.global start\nstart:\n" + "\n".join(ASM) + "\n")
        subprocess.run(["clang", "--target=aarch64-none-elf", "-c", str(p / "probe.s"),
                        "-o", str(p / "probe.o")], check=True, capture_output=True)
        subprocess.run(["llvm-objcopy", "-O", "binary", "--only-section=.text",
                        str(p / "probe.o"), str(p / "probe.bin")],
                       check=True, capture_output=True)
        content = (p / "probe.bin").read_bytes()
    assert len(content) == 4 * len(ASM)
    return struct.unpack("<%dI" % len(ASM), content)


def load_nso(path: Path, build: str) -> bytes:
    data = path.read_bytes()
    if data[:4] != b"NSO0" or data[0x40:0x54].hex().upper() != build:
        raise ValueError("incorrect build ID or NSO header")
    for i in range(3):
        _, segment, length = struct.unpack_from("<III", data, 0x10 + 16 * i)
        start = 0x100 + segment
        if start + length > len(data):
            raise ValueError("truncated NSO segment")
        if hashlib.sha256(memoryview(data)[start:start+length]).digest() != data[0xA0+32*i:0xC0+32*i]:
            raise ValueError("NSO segment hash mismatch; use original decompressed NSO")
    return data


def find_caves(data: bytes, anchor: int, instruction_count: int):
    text_size = struct.unpack_from("<I", data, 0x18)[0]
    text = data[0x100:0x100+text_size]
    caves = []
    for m in re.finditer(b"\x00{16,}", text):
        first, last = m.span()
        start = (first + 3) & ~3
        capacity = (last - start) // 4 - 1
        if capacity < 3:
            continue
        previous = struct.unpack_from("<I", text, start - 4)[0]
        if previous in (0xD65F03C0, 0xD65F0FFF, 0xD65F0BFF) or previous >> 26 == 0b000101:
            caves.append((start, capacity))
    caves.sort(key=lambda c: (abs(c[0]-anchor) // 0x800000, -c[1], abs(c[0]-anchor)))
    chosen, capacity = [], 0
    for item in caves:
        chosen.append(item)
        capacity += item[1]
        if capacity >= instruction_count:
            break
    if capacity < instruction_count:
        raise ValueError("no sufficiently isolated executable padding")
    return chosen


def patch_for(path: Path, build: str, compiled: tuple[int, ...]):
    data = load_nso(path, build)
    conf = BUILDS[build]
    hook = conf["delta_hook"]
    caves = find_caves(data, hook, len(compiled))
    records = {}

    def add(offset, expected, replacement):
        original = struct.unpack_from("<I", data, 0x100 + offset)[0]
        if offset in records or original != expected:
            raise ValueError(f"conflicting or unexpected opcode at main+0x{offset:08X}")
        records[offset] = replacement

    pos, used = 0, []
    for n, (start, capacity) in enumerate(caves):
        if pos == len(compiled):
            break
        count = min(capacity, len(compiled)-pos)
        used.append((start, count))
        for i, opcode in enumerate(compiled[pos:pos+count]):
            add(start+4*i, 0, opcode)
        pos += count
        next_pc = caves[n+1][0] if pos < len(compiled) else hook+4
        add(start+4*count, 0, encode_b(start+4*count, next_pc))
    assert pos == len(compiled)
    add(conf["guard"], EXPECTED["guard"], 0xD503201F)
    add(conf["present"], EXPECTED["present"], 0x52800021)
    add(hook, EXPECTED["delta_hook"], encode_b(hook, used[0][0]))
    assert struct.unpack_from("<I", data, 0x100+hook-4)[0] == 0x1E220C21
    assert struct.unpack_from("<I", data, 0x100+hook+4)[0] == 0x37080289
    assert decode_b(hook, records[hook]) == used[0][0]
    assert decode_b(used[-1][0]+4*used[-1][1],
                    records[used[-1][0]+4*used[-1][1]]) == hook+4
    ips = bytearray(b"IPS32")
    for at, opcode in sorted(records.items()):
        ips.extend(struct.pack(">IH", at+0x100, 4))
        ips.extend(struct.pack("<I", opcode))
    ips.extend(b"EEOF")
    return bytes(ips), used


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e0f3", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("dist/oot-v9-local-test.zip"))
    args = parser.parse_args()
    compiled = assemble()
    files = {}
    for build, nso in zip(BUILDS, (args.e0f3, args.base)):
        ips, caves = patch_for(nso, build, compiled)
        files[f"{TITLE}/{MOD}/exefs/{build}.ips"] = ips
        print(f"{build[:8]}: {len(ips)} IPS bytes, cave locations: "
              + ", ".join(hex(at) for at, _ in caves))
    files[f"{TITLE}/{MOD}/README.txt"] = (
        "V9: experimental elapsed-frame-time timing PROBE, not a final mod.\n"
        "No gameplay validation yet. For testing with backed-up saves only.\n"
        "Disable all other FPS patches including Orchid's built-in version.\n"
        "Use 100% emulator speed and disable frame generation.\n"
        "Tests whether menus, loading and gameplay retain normal speed at 15-60 FPS.\n"
        "Large delays are clamped to 4 simulation ticks; below 15 FPS may run slow.\n"
        "No game binaries or other game assets are included.\n"
    ).encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(files.items()):
            archive.writestr(name, payload)
    with zipfile.ZipFile(args.output) as archive:
        assert archive.testzip() is None
        assert all(archive.read(k) == v for k, v in files.items())
    print(args.output)


if __name__ == "__main__":
    main()
