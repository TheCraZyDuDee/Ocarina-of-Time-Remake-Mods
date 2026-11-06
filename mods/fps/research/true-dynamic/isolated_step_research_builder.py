#!/usr/bin/env python3
"""E0F3 ISOLATED-SIMULATION-STEP RESEARCH BUILDER (UNVALIDATED).

Not a finished dynamic FPS mod. This first research candidate changes
ONLY the original E0F3 FDIV S8 simulation multiplier, preserving both
the unmodified interval-controller guard and the unmodified presentation
interval. It reuses the audited V9 read-only elapsed-step helper but
INTENTIONALLY DOES NOT reproduce failed V9's other two controller edits.

No output is created unless the user explicitly opts into research
build generation with their own original DECOMPRESSED, hash-verified NSO.
Never commit game binaries, experimental IPS, ZIPs or private dumps.
Only create a local, backup-protected candidate; gameplay validity
must be independently tested at 15/30/45/60 FPS before any release.
"""
import argparse
from pathlib import Path
import struct
import zipfile

import real_elapsed_probe_builder as previous

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
TITLE = previous.TITLE
RESEARCH_MOD = "Isolated Step (UNVALIDATED Research)"
CONFIG = previous.BUILDS[BUILD]

ORIGINAL_DIV = previous.EXPECTED["delta_hook"]
ORIGINAL_GUARD = previous.EXPECTED["guard"]
ORIGINAL_PRESENT = previous.EXPECTED["present"]
DIV_NUMERATOR = 0x1E220C21
DIV_NEXT_BRANCH = 0x37080289


def verified_original(data):
    """Fail if target is not an unmodified original decompressed NSO."""
    expected = {
        CONFIG["guard"]: ORIGINAL_GUARD,
        CONFIG["present"]: ORIGINAL_PRESENT,
        CONFIG["delta_hook"] - 4: DIV_NUMERATOR,
        CONFIG["delta_hook"]: ORIGINAL_DIV,
        CONFIG["delta_hook"] + 4: DIV_NEXT_BRANCH,
    }
    for offset, opcode in expected.items():
        if offset < 0 or 0x100 + offset + 4 > len(data):
            raise ValueError("Original module is too short for E0F3 site validation")
        actual = struct.unpack_from("<I", data, 0x100 + offset)[0]
        if actual != opcode:
            raise ValueError(f"Unmodified E0F3 opcode mismatch at main+0x{offset:08x}")


def construct_ips(data, helper_words, *, cave_picker=None):
    verified_original(data)
    if not 1 <= len(helper_words) <= 128:
        raise ValueError("Unsafe helper length")
    if cave_picker is None:
        cave_picker = previous.find_caves
    hook = CONFIG["delta_hook"]
    caves = cave_picker(data, hook, len(helper_words))
    if not caves:
        raise ValueError("No verified code cave available")
    records = {}
    used = []
    pos = 0

    def write_opcode(offset, expected_original, replacement):
        if offset in records or offset < 0 or 0x100 + offset + 4 > len(data):
            raise ValueError("Unsafe or duplicate patch offset")
        original = struct.unpack_from("<I", data, 0x100 + offset)[0]
        if original != expected_original:
            raise ValueError(f"Unexpected original instruction at main+0x{offset:08x}")
        records[offset] = replacement

    for index, (offset, capacity) in enumerate(caves):
        if pos >= len(helper_words):
            break
        if capacity < 1 or offset & 3:
            raise ValueError("Invalid code-cave region")
        count = min(capacity, len(helper_words)-pos)
        used.append((offset, count))
        for i in range(count):
            write_opcode(offset + 4 * i, 0, helper_words[pos+i])
        pos += count
        next_addr = (caves[index+1][0] if pos < len(helper_words)
                     else hook + 4)
        write_opcode(offset + 4 * count, 0,
                     previous.encode_b(offset + 4 * count, next_addr))
    if pos != len(helper_words):
        raise ValueError("Insufficient code-cave capacity")
    write_opcode(hook, ORIGINAL_DIV, previous.encode_b(hook, used[0][0]))

    # Enforce non-overlap with BOTH unmodified controller edits; V9's two
    # controller changes must NEVER leak into the isolated candidate.
    if CONFIG["guard"] in records or CONFIG["present"] in records:
        raise ValueError("Refusing to patch controller guard/presentation site")
    if len(records) != len(helper_words) + len(used) + 1:
        raise ValueError("Unexpected number of IPS instruction records")
    if previous.decode_b(hook, records[hook]) != used[0][0]:
        raise ValueError("Hook branch mismatch")
    if previous.decode_b(used[-1][0] + 4 * used[-1][1],
                         records[used[-1][0] + 4 * used[-1][1]]) != hook + 4:
        raise ValueError("Trampoline return branch mismatch")

    ips = bytearray(b"IPS32")
    for at, opcode in sorted(records.items()):
        ips += struct.pack(">IH", at + 0x100, 4) + struct.pack("<I", opcode)
    ips += b"EEOF"
    return bytes(ips), used, records


def generate_zip(nso_path, out_path):
    data = previous.load_nso(nso_path, BUILD)
    words = previous.assemble()
    ips, caves, records = construct_ips(data, words)
    readme = (
        "ISOLATED STEP RESEARCH - UNVALIDATED EXPERIMENT\n"
        "NOT A FINISHED DYNAMIC FPS MOD; DO NOT USE FOR NORMAL PLAY.\n"
        "E0F3 ONLY; do not install on 33FA. Back up all saves first.\n"
        "Disable other FPS patches; use 100% emulator speed; no frame generation.\n"
        "Unlike FAILED V9, patches ONLY original FDIV S8 and code caves.\n"
        "Retains original frame guard and presentation interval unmodified.\n"
        "No gameplay speed, collision, animation or scene transition validation.\n"
        "Expected original game slow motion under 60 FPS; goal is to correct\n"
        "simulation advancement without changing presentation pacing.\n"
        "The result is an ISOLATION TEST, not a verified solution.\n"
    ).encode()
    files = {
        f"{TITLE}/{RESEARCH_MOD}/exefs/{BUILD}.ips": ips,
        f"{TITLE}/{RESEARCH_MOD}/README.txt": readme,
    }
    out_path = Path(out_path)
    if out_path.exists():
        raise ValueError("Refusing to overwrite existing research ZIP")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "x", zipfile.ZIP_DEFLATED) as z:
        for name, payload in sorted(files.items()):
            z.writestr(name, payload)
    with zipfile.ZipFile(out_path) as z:
        if z.testzip() is not None or any(z.read(k) != v for k,v in files.items()):
            raise RuntimeError("Research ZIP roundtrip verification failed")
    return {"zip_path": str(out_path), "ips_bytes": len(ips),
            "ips_instruction_records": len(records), "code_cave_segments": len(caves)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--e0f3", type=Path, required=True,
                   help="Original, decompressed, segment-hash-verified E0F3 NSO")
    p.add_argument("--output", type=Path, default=Path("private-isolated-step-research.zip"))
    p.add_argument("--enable-unvalidated-research-build", action="store_true")
    args = p.parse_args()
    if not args.enable_unvalidated_research_build:
        p.error("UNVALIDATED candidate: explicit --enable-unvalidated-research-build "
                "required; do not publish or use as a finished mod")
    print(generate_zip(args.e0f3, args.output))
    print("Private research output only; do NOT commit this ZIP/IPS to GitHub.")


if __name__ == "__main__":
    main()
