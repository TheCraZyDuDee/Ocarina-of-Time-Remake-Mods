#!/usr/bin/env python3
"""One-command LOCAL E0F3 original-ZBIC -> verified inspection -> research IPS.

This combines existing private NSO unpacking and the step-only experimental
IPS builder. It does NOT save decompressed source code to disk: decoding
occurs in RAM and checks ALL three original per-segment SHA-256 digests.
Requires an independently installed 'zbic' Python package and LLVM/clang
for assembling new, independently authored helper instructions.
No Nintendo executables or keys are uploaded or bundled.

Only a private, explicitly enabled, UNVALIDATED mod test ZIP is emitted.
The game has not been proved normal-speed at arbitrary FPS. Disable all
other FPS mods and back up saves before separately testing this prototype.
"""
import argparse
from pathlib import Path
import hashlib
import json
import zipfile

from inspection_image_validation import validate_inspection_image
from private_nso_inspection_image import inspect_header, make_inspection_image
from isolated_step_research_builder import BUILD, generate_zip_from_image


def create_from_original_zbic(original_path: Path, out_path: Path):
    original_path = Path(original_path)
    out_path = Path(out_path)
    if original_path.resolve() == out_path.resolve():
        raise ValueError("Input and output must be different files")
    if out_path.exists():
        raise ValueError("Research ZIP already exists; refusing to overwrite")
    original = original_path.read_bytes()
    flags, segments = inspect_header(original)
    if original[0x40:0x54].hex().upper() != BUILD:
        raise ValueError("This isolated research prototype supports E0F3 only")
    if flags & 0x87 != 0x87 or not all(s["compressed"] for s in segments):
        raise ValueError("Expected original E0F3 ZBIC-compressed NSO")
    for section in segments:
        at = section["file_offset"]
        if original[at:at+4] != b"ZBIC":
            raise ValueError(f"{section['name']} does not have original ZBIC signature")
    # The only decompression stage. make_inspection_image validates all
    # three section digests before returning, and does not write files.
    image, decoded_build = make_inspection_image(original)
    if decoded_build != BUILD:
        raise ValueError("Unexpected decoded original E0F3 identity")
    verified_sections = validate_inspection_image(image, BUILD)
    result = generate_zip_from_image(image, out_path)
    with zipfile.ZipFile(out_path) as bundle:
        ips_entries = [name for name in bundle.namelist()
                       if name.lower().endswith(".ips")]
        if len(ips_entries) != 1 or bundle.testzip():
            raise RuntimeError("Unexpected or corrupt research package")
        ips_digest = hashlib.sha256(bundle.read(ips_entries[0])).hexdigest()
    # Structural metadata only; NEVER serialize original or decoded NSO.
    return {
        **result, "build_id": BUILD, "original_nso_sha256": hashlib.sha256(original).hexdigest(),
        "verified_segment_names": [x["section"] for x in verified_sections],
        "ips_sha256": ips_digest,
        "status": "UNVALIDATED RESEARCH BUILD — not safe for normal play",
        "private": "Do not publish the original NSO or the private test ZIP",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-zbic", type=Path, required=True,
                        help="Your private original compressed E0F3 NSO file (e.g. main(1))")
    parser.add_argument("--output", type=Path, default=Path("private-isolated-step-research.zip"))
    parser.add_argument("--enable-unvalidated-research-build", action="store_true")
    args = parser.parse_args()
    if not args.enable_unvalidated_research_build:
        parser.error("Explicit --enable-unvalidated-research-build required; "
                     "this is NOT a verified FPS mod")
    result = create_from_original_zbic(args.original_zbic, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
