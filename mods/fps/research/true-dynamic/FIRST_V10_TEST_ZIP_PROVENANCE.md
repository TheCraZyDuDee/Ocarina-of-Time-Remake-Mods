# First E0F3 isolated-step experimental ZIP — actually generated (2026-11-06)

**Research prototype; NOT a proven working dynamic-FPS mod.**

An E0F3-only experimental IPS32 ZIP was built locally using the
tester-owned **previous V9 research ZIP** recovered from the user's
private File Library. This bypassed the ZBIC decompression blocker:
the archived V9 ZIP already contains an independently authored,
executable code-cave trampoline which the original V9 source created
only after validating the user's original decompressed E0F3 NSO
SHA-256 segment hashes and original instruction/cave layout.
We therefore reused the exact **E0F3 helper** rather than guessing
unmapped cave addresses or publishing the compressed game binary.

The local output is:

`OOT_Remake_True_Dynamic_FPS_Isolated_Step_E0F3_V10_TEST.zip`

It was delivered as a private chat sandbox artifact, **not pushed to
GitHub and not released to the stable branch**.

## What changed from known-failed V9

The original V9 E0F3 IPS contained **22 four-byte IPS records**.
Exactly these *two* controller modifications were removed:

| Offset | V9 changed behavior | This build |
| --- | --- | --- |
| `main+0x03B4EF90` | NOP of the original `TBNZ` controller gate | **Unmodified original** |
| `main+0x03B4F080` | `MOV W1,#1` instead of controller interval | **Unmodified original** |

The new IPS contains **20 four-byte records**:
**one** B branch replacing original `FDIV S8,S1,S0` at
E0F3 `main+0x006E6CC4`, **16** independently authored helper
instructions in three original V9 code caves, and **three** B
instructions connecting those caves back to `hook+4`.

The helper chain is:

```text
main+0x006E6CC4 -> 0x006E1864 -> 0x006E0F04
                -> 0x006F1804 -> 0x006E6CC8
```

It reads the previously traced frame-like counter duration from the
original timing state, scales by nominal rate / CNTFRQ_EL0, and clamps
the resulting step between 0.5 and 4.0. It is the **same** helper
from known-failed V9; removing the two controller changes **isolates**
a causal hypothesis but does NOT prove that V9's observed excess
speed will disappear.

## Exact locally verified source provenance

- Original private V9 ZIP SHA-256:
  `061d7d2fccf0d657a64ffa8e4b1c789efa16c056810c359137b6593b5fd08178`.
- Original E0F3 V9 IPS SHA-256:
  `207519e2fe0bb2895732b6d5f8e43fbf3d5f90af32f2df36650192438c02f847`.
- Recovered independently authored 16-instruction helper SHA-256:
  `dd727cf48abe8c609be9bb065ad721bb1104bb2c9c87e877916f92c6e0d414b6`.
- Final E0F3 isolated IPS SHA-256:
  `306e36cec3efc28a38df627ed38245fe29008855a85cfe4a249a7d8fb2fd1365`.
- Final IPS length: **209 bytes** (5-byte header,
  20 records of 10 bytes, 4-byte `EEOF`).
- Final private test ZIP SHA-256:
  `82489acb9aeb8876d69a898c4f2d4adc9b3f36ddc059f1c5cd50a264653d8b9c`.
- Final private ZIP contains **exactly** the E0F3 IPS,
  a clear `README.txt`, and `AUDIT.json` recording hashes and
  untested status. It contains no NSO, keys, save data, or 33FA IPS.

Offline local checks passed: source archive integrity and IPS
length/structure; 22 original records with only the two expected
controller edits removed; strict remaining offset-set match;
full 4-branch trampoline target checks; helper machine-code bytes
reassembled from the authored AArch64 `ASM` and **matched all
16 source instructions**; regenerated IPS parse/serialize roundtrip;
output ZIP CRC and contents.

**Limitations:** these static checks cannot ensure correct gameplay
speed, collision, animation or pacing. This is an *installable first
experimental build*, not a working finished mod. No Eglantine
runtime execution from this container was possible. The user must
test actual simulation speed at 60, 45, 30 and 15 FPS using backed-up
saves, all other FPS mods disabled, emulator speed at 100%, and no
frame-generation features. Revert immediately if game time runs fast
or slow. The 33FA build lacks independently mapped downstream
logic and is intentionally excluded.

## Why this resolves the decompression deadlock for this experiment

Previously we attempted to install a ZBIC decoder in a network-
restricted execution container. The user's original E0F3/33FA NSOs
are present but compressed; a real decoder could not be installed.
The File Library also contained the *already-built* V9 ZIP with its
verified code caves and self-contained helper. Transforming that
IPS by removing the two independently identified controller
changes permitted actual experimental packaging **without
decompressing either original NSO in this session**.

No raw original Nintendo game instructions or private NSOs were
uploaded to GitHub. All changes are limited to
`research/true-dynamic-fps`; the private binary remains in chat.
