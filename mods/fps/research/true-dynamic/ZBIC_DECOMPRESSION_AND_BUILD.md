# Reproducible ZBIC decoding and first private research build (2026-11-06)

**Status:** Real original NSO headers and compressed segment signatures verified.
The complete decoding/building path has passed **synthetic end-to-end CI**,
but the current restricted analysis container could not install the external
ZBIC package. **No actual IPS ZIP from the user's original executable has
yet been produced or gameplay-validated.** Do not imply otherwise.

## Why the earlier work was "good enough"

An earlier research script already existed:
[\`private_nso_inspection_image.py\`](private_nso_inspection_image.py).
It parses a private original Nintendo NSO, decodes compressed segments,
verifies all three SHA-256 digests stored in the NSO header, and makes a
**non-runnable, inspection-only** memory-layout image. That image has
segment bytes at \`0x100 + NSO.memory_offset\`, so original AArch64
instruction offsets (e.g. E0F3 \`main+0x006E6CC4\`) can be read at
\`0x100 + instruction_offset\`.

**Important:** a decoded inspection image is not a genuine, loadable,
decompressed NSO. Its 0x100-byte header retains the original **compressed
file** offsets/flags/sizes for verification/provenance, but the code and
data are laid out at **virtual memory offsets** after the header.
The earlier archived V9 builder's \`load_nso\` assumes an incompatible
file-offset layout. Feeding that inspection image into that function
would check the wrong bytes and fail or be misleading.

The present research fixes the discrepancy with
[\`inspection_image_validation.py\`](inspection_image_validation.py):
it verifies each decoded region at \`0x100 + memory_offset\` against
the **original header SHA-256**, enforces non-overlapping ordered
regions, correct image length, E0F3 build ID and original compression
flags. The *isolated research builder*, not the archived failed V9
builder, now consumes this verified memory image.

A new wrapper,
[\`build_isolated_from_original_zbic.py\`](build_isolated_from_original_zbic.py),
performs all steps **in RAM**:

1. Parse original ZBIC NSO header and identify the E0F3 build ID.
2. Check all three original compressed section signatures are \`ZBIC\`.
3. Invoke independently installed Kinnay \`zbic.decompress\` for each
   section; verify its **uncompressed length and original SHA-256**.
4. Revalidate the memory-layout image against all three hashes.
5. Assemble independently authored, **step-only** experimental helper
   and patch **only the original E0F3 FDIV hook + verified code caves**.
   Both original V9 controller locations must be unchanged and must
   not appear as patch records.
6. Create one explicitly labeled **unvalidated/private IPS32 test ZIP**;
   verify ZIP integrity and print the original NSO SHA-256,
   IPS SHA-256 and structural metadata only.

The wrapper **does not write a decompressed Nintendo NSO to disk**.
It will reject a wrong build, modified instruction fingerprints,
bad section hashes, unsafe/missing code caves, and existing output
filename. It emits **no game binary** into the ZIP. All source-only
pipeline tests use synthetic NSO sections and a mock ZBIC codec,
not copyrighted code.

## What is ZBIC? (independently researched)

Nintendo introduced ZBIC in Switch system version **22.0.0**.
It is a modified Zstandard stream. The magic bytes are ASCII
\`ZBIC\` (\`0x4349425A\` as little-endian u32), instead of ordinary
Zstandard's magic. Its FSE entropy tables use
**Binary Interpolative Coding**, not the ordinary zstd representation.
NSO header flags bit 7 selects ZBIC for compressed sections; bits
0–2 continue to indicate per-section compression.
**Do not** replace the \`ZBIC\` magic with normal zstd magic and try
\`zstd -d\`; a header change does not fix the BIC table coding.

References (external, retrieved 2026-11-06):

- Nintendo Switch Brew 22.0.0 loader section:
  https://www.switchbrew.org/wiki/22.0.0
- Kinnay's GPL-2.0 ZBIC Python decoder:
  https://github.com/kinnay/zbic
- Published \`zbic==1.0.1.post1\` distributions (including
  CPython 3.13 Linux manylinux wheels):
  https://pypi.org/project/zbic/1.0.1.post1/
- Eden emulator's merged support, PR #4482 (2026-09-27):
  https://git.eden-emu.dev/eden-emu/eden/pulls/4482

**Dependency licensing:** Kinnay's decoder is GPLv2, independently
provided. We only **import** it at runtime on the user's private
system. Do not vendor, relicense, redistribute or commit the decoder,
the original NSOs or any decompressed game code into this repository.

## Private original executable header verification (already done)

Two original NSO uploads were inspected **locally and privately**.
Both NSO headers have flags \`0xFF\`, three ZBIC-compressed segments,
and physically begin each section at the declared compressed
\`file_offset\`. These are reference structural facts, not copied code:

| NSO build | Source file SHA-256 | Compressed section file offsets | Header decompressed TEXT size |
| --- | --- | --- | --- |
| E0F3 | \`7db9ddfda088c22d219ef13496decd7077c68cd67d4b37f53f4ac46a082768f2\` | \`0x104\`, \`0x17342EB\`, \`0x1BDB1C6\` | \`0x3C461D0\` |
| 33FA | \`efe7b93dfacb091fa0948a92152fd014962a498e463114a924c265522397d990\` | \`0x104\`, \`0x171C4C2\`, \`0x1BC0281\` | \`0x3BE6850\` |

A local header check can reproduce these without decompressing:
\`struct.unpack_from('<I', nso, 0xc)\` for flags,
\`struct.unpack_from('<III', nso, 0x10+16*i)\` for
\`(file_offset, memory_offset, decompressed_size)\`, and
\`nso[file_offset:file_offset+4] == b'ZBIC'\` for each section.
The original per-section hash is at \`0xA0+32*i\`.
**A header check alone is NOT proof the decompression works**;
only successful decoding and all three SHA-256 matches establish that.

## One-shot private Linux build (CachyOS)

Keep the original \`main(1)\` file on the user's machine;
the command should point to its **actual private location**.
Clone only the research branch and create a virtual environment
(avoids Arch's externally managed system Python). Internet access
is required on that machine to obtain the external \`zbic\` wheel.
The build also needs \`clang\` and \`llvm-objcopy\` installed;
the local package for the latter is generally \`llvm\`.

\`\`\`bash
git clone --depth 1 --branch research/true-dynamic-fps \
  'https://github.com/TheCraZyDuDee/Ocarina-of-Time-Remake-Mods.git' \
  "$HOME/oot-dynamic-fps-research"
cd "$HOME/oot-dynamic-fps-research"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'zbic==1.0.1.post1'
python mods/fps/research/true-dynamic/build_isolated_from_original_zbic.py \
  --original-zbic '/ACTUAL/PRIVATE/PATH/TO/main(1)' \
  --output "$HOME/private-isolated-step-research.zip" \
  --enable-unvalidated-research-build
\`\`\`

If the repository was already cloned to that location, use
\`git -C "$HOME/oot-dynamic-fps-research" fetch origin research/true-dynamic-fps\`
and \`git -C ... checkout research/true-dynamic-fps\` rather than
recloning. Do **not** run this on \`main\` or publish generated IPS ZIPs.

**Output remains an UNVALIDATED research experiment.** Its generator
reuses the archived V9's *wall-clock step helper*, without V9's
controller guard/presentation edits. That isolates a hypothesis but
does NOT prove the step's runtime freshness or correct behavior
under 30 FPS gameplay. Back up saves, disable all other FPS mods,
use emulator speed 100%, and treat this as an instrumented first test,
not a new release.

A lower-level two-step route also works with the existing
\`private_nso_inspection_image.py\` to save a local inspection image
first, then \`isolated_step_research_builder.py --e0f3 IMAGE\`.
This is less desirable: it leaves a large decrypted/decompressed
inspection file on disk and has more room for user errors.
Use the one-shot wrapper instead.

## CI coverage and current limitations

- \`tests/test_private_nso_inspection_image.py\`: synthetic
  LZ4/uncompressed/ZBIC-stub decoding and original hash failures.
- \`tests/test_zbic_to_research_build.py\`: synthetic original
  ZBIC -> decoded memory-offset image -> 3 section SHA-256
  validation -> isolated IPS ZIP, with negative tests.
- \`tests/test_isolated_step_research_builder.py\`: exact original
  hook/controller requirements, cave length/ranges, ZIP content and
  overwrite rejection.

These tests have **not** decrypted or decompressed the user's private
real E0F3 NSO in the CI runner. The current ChatGPT container has
no network DNS and no installed ZBIC wheel, so it cannot honestly
claim a successful real-NSO decode or provide a verified installable
binary here. However, all necessary source and dependencies for the
user's private Linux local workflow have been identified.

**Prioritize the first private experimental build, not more GDB
capture requests.** Once a real local build passes the original
three segment hashes and exact opcode/cave checks, test its gameplay
at around 60/45/30/15 FPS with 100% emulator speed. Keep
\`research/true-dynamic-fps\` isolated until empirically validated.
