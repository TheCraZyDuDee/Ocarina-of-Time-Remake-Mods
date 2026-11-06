#!/usr/bin/env python3
"""Build all FPS ZIPs from independently authored ARM64 replacement words.

The True Dynamic E0F3 IPS is byte-for-byte the successful user-tested V10
simulation-step patch. No Nintendo game executables or keys are required.
"""
from pathlib import Path
import argparse
import hashlib
import struct
import zipfile

TITLE_ID = "0400486024DEC000"
HEADER = 0x100
E0F3 = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
BASE = "33FA6C2C23848282A77E8B88A0A93F4887C55920"

BUILDS = {
    E0F3: {
        "fixed": ((0x3B4F004, 0x1A89B10A, 0x5280004A),
                  (0x3B4F370, 0x52800788, 0x52800041),
                  (0x3B4F37C, 0x1AC10D08, 0x528003C8)),
        "adaptive": ((0x3B4EF90, 0x37000728, 0xD503201F),),
    },
    BASE: {
        "fixed": ((0x3AF1994, 0x1A89B10A, 0x5280004A),
                  (0x3AF1D00, 0x52800788, 0x52800041),
                  (0x3AF1D0C, 0x1AC10D08, 0x528003C8)),
        "adaptive": ((0x3AF1920, 0x37000728, 0xD503201F),),
    },
}
MODES = {
    "fixed-30": ("Fixed 30 FPS", "Fixed 30 FPS, native time-step; tested at normal speed on the E0F3 build."),
    "adaptive": ("Adaptive FPS (Native 20-30-60)", "Experimental native adaptive 20/30/60 FPS. The 20 FPS mode has been tested."),
    "true-dynamic": ("True Dynamic FPS (E0F3)", "E0F3-only isolated simulation-step timing. User reports normal game speed around 10-45 actual FPS; other builds/scenes not fully tested."),
}
OUTPUT_NAMES = {
    "fixed-30": "oot-fixed-30-both-builds.zip",
    "adaptive": "oot-adaptive-both-builds.zip",
    "true-dynamic": "oot-true-dynamic-e0f3.zip",
}
EXPECTED_PATCH_SHA256 = {
    "fixed-30": {E0F3:"3864fad59983c9ed459d68447578f72aedb8bd10e3ebd604c017d87c6f99c8f6", BASE:"9494a3d6d6d779349aa945814447b239a10f038e8978b79f15ddd598d34119b3"},
    "adaptive": {E0F3:"009cad39a78862dd8ea974b24bbdd40ab6843a14db219b239bcb016457b96f40", BASE:"0f3eb6c5eb34ffdd989c3f23a0e599703eb4e617d06845397e945f8457903564"},
    "true-dynamic": {E0F3:"306e36cec3efc28a38df627ed38245fe29008855a85cfe4a249a7d8fb2fd1365"},
}

# Exactly the 16 independently authored V10 helper instructions already
# playtested. Guard at main+0x03B4EF90 and presentation at +0x03B4F080
# MUST remain unchanged. Three original code caves were source verified.
DYNAMIC_HOOK = 0x006E6CC4
ORIGINAL_DIV = 0x1E201828
DYNAMIC_CAVES = (
    (0x006E1864, (0xF81F0FE8, 0xFC1F0FE0, 0xF9405668, 0xF9401108, 0xF9408108, 0x9E220108)),
    (0x006E0F04, (0xD53BE008, 0x9E220100, 0x1E210908, 0x1E201908, 0x1E2C1000, 0x1E206908)),
    (0x006F1804, (0x1E221000, 0x1E207908, 0xFC4107E0, 0xF84107E8)),
)

def branch(source, target):
    difference = target - source
    if difference % 4 or not -(1 << 27) <= difference < (1 << 27):
        raise ValueError("ARM64 B target outside range")
    return 0x14000000 | ((difference // 4) & 0x3FFFFFF)

def patches_for(mode, build_id):
    if mode not in MODES:
        raise ValueError("Unknown mode")
    if build_id not in EXPECTED_PATCH_SHA256[mode]:
        raise ValueError("Unsupported executable build for this FPS mod")
    if mode == "fixed-30":
        return BUILDS[build_id]["fixed"]
    if mode == "adaptive":
        return BUILDS[build_id]["adaptive"]
    edits = [(DYNAMIC_HOOK, ORIGINAL_DIV, branch(DYNAMIC_HOOK, DYNAMIC_CAVES[0][0]))]
    for index, (start, words) in enumerate(DYNAMIC_CAVES):
        for i, word in enumerate(words):
            edits.append((start + i*4, 0, word))
        next_pc = DYNAMIC_CAVES[index+1][0] if index+1 < len(DYNAMIC_CAVES) else DYNAMIC_HOOK+4
        edits.append((start+len(words)*4, 0, branch(start+len(words)*4, next_pc)))
    if len(edits) != 20 or any(a in (0x03B4EF90, 0x03B4F080) for a,_,_ in edits):
        raise AssertionError("V10 controller isolation invariant violated")
    return tuple(edits)

def ips32(edits):
    out = bytearray(b"IPS32")
    seen = set()
    for address, original, replacement in sorted(edits):
        if address % 4 or address < 0 or address in seen:
            raise ValueError("Invalid or repeated IPS offset")
        seen.add(address)
        out += struct.pack(">IH", address+HEADER, 4)
        out += struct.pack("<I", replacement)
    return bytes(out+b"EEOF")

def parse_ips32(data):
    if not data.startswith(b"IPS32") or not data.endswith(b"EEOF"):
        raise ValueError("Invalid IPS32")
    pos, records, end = 5, {}, len(data)-4
    while pos < end:
        if pos+10 > end:
            raise ValueError("Incomplete IPS32 entry")
        address, size = struct.unpack_from(">IH", data, pos)
        if address < HEADER or size != 4:
            raise ValueError("Invalid IPS32 entry")
        address -= HEADER
        if address % 4 or address in records:
            raise ValueError("Repeated or unaligned IPS32 entry")
        records[address] = struct.unpack_from("<I", data, pos+6)[0]
        pos += 10
    if pos != end:
        raise ValueError("Invalid IPS32 length")
    return records

def archive_readme(mode):
    name, description = MODES[mode]
    ids = EXPECTED_PATCH_SHA256[mode]
    return (
        f"{name}\n\n{description}\n\n"
        f"Game title ID: {TITLE_ID}\n"
        "Supported main build IDs:\n" + "\n".join(ids) + "\n\n"
        "Install this ZIP via a supported emulator mod manager, or copy the inner\n"
        f'"{name}" folder into load/{TITLE_ID}/.\n'
        "Enable only ONE FPS mod at a time. Disable Orchid built-in FPS patch.\n"
        "Restart the game with the speed limiter at 100% and frame generation off.\n"
        "Check the emulator log to confirm the IPS was applied. Back up saves.\n"
        "No game executable or game assets are distributed.\n"
    ).encode("utf-8")

def build(output_dir, modes=tuple(MODES)):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for mode in modes:
        name, _ = MODES[mode]
        files = {}
        for build_id, digest in EXPECTED_PATCH_SHA256[mode].items():
            edits = patches_for(mode, build_id)
            payload = ips32(edits)
            if parse_ips32(payload) != {a:b for a,_,b in edits}:
                raise AssertionError("IPS32 structural check failed")
            if hashlib.sha256(payload).hexdigest() != digest:
                raise AssertionError(f"Original IPS32 SHA-256 drift for {mode}/{build_id}")
            files[f"{TITLE_ID}/{name}/exefs/{build_id}.ips"] = payload
        files[f"{TITLE_ID}/{name}/README.txt"] = archive_readme(mode)
        target = output_dir/OUTPUT_NAMES[mode]
        with zipfile.ZipFile(target, "w") as z:
            for filename, data in sorted(files.items()):
                info = zipfile.ZipInfo(filename, date_time=(1980,1,1,0,0,0))
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o644 << 16
                z.writestr(info, data)
        with zipfile.ZipFile(target) as z:
            if z.testzip() is not None or any(z.read(k) != v for k,v in files.items()):
                raise AssertionError("ZIP integrity or content check failed")
        results.append(target)
    return results

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, default=Path("dist"))
    p.add_argument("--mode", choices=tuple(MODES)+("all",), default="all")
    args = p.parse_args()
    for path in build(args.output_dir, tuple(MODES) if args.mode=="all" else (args.mode,)):
        print(path)
