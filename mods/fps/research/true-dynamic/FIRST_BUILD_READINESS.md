# First experimental dynamic-FPS build: readiness and validation gates

**As requested by the tester: when research supports it, produce the first
actual installable mod build—not just another analysis note.**

The first *experimental* build is deliberately an **isolated step**
experiment on **E0F3 only**. **It now has a positive user gameplay
report (2026-11-07) at roughly 10–15 and 30–45 actual FPS**, but
has not been independently timed across the whole game or ported to
33FA. It must never be silently published to `main`/stable releases.
The goal remains dynamic FPS without slow-motion or sped-up gameplay
at variable *actual* rendering rates.

## Source-level evidence available (2026-11-06)

1. Original unmodified gameplay at approximately 30 actual FPS runs in
   slow motion. The original timing configuration remains
   `step=1.0`, nominal=60, and the frame-context counters progress
   at ~30 units per requested free-running second.
2. Original `X21+0x100` is a frame-like guest physical counter delta,
   averaging 33.450 ms in sparse original ~30 FPS gameplay samples.
   The ~50 FPS capture also scales plausibly. It cannot be treated
   as a cumulative 4-clamp timer on the basis of those samples.
3. The original frame-step hook at E0F3 `main+0x006E6CC4`
   produces `S8=1.0` for 60 nominal FPS, and feeds
   `main+0x03B4E300` timing config on the active call path.
4. The callback is **present** and the newly verified 4096-byte
   `main+0x02F52DF0` source window shows it loads the variable
   step from config`+0x10`, rounds steps for integer object
   countdowns, performs step-multiplied float interpolation,
   and computes other event/time-scale values. Thus fractional or
   multi-unit steps have explicit downstream implementations,
   although not all whole-engine physics is verified.
5. The native presentation setter at `main+0x0346C5C0` both sends
   the argument interval to a lower-level setter and writes
   **`timing+0xFC = 60/interval`** (60 when interval=0).
6. V9 changed *three* sites: original guard, presentation argument
   and frame-step divide. Its forced present interval 1 could
   contradict rate setting derived from stored interval. Its
   over-speed is real and should not be repeated.
7. Original native FPS setter at `main+0x004DC0F0` has the
   normal divisor-of-60 rule and a special state-gated branch
   accepting some >=40 requests without that ordinary test.

## Candidate and guardrails

[`isolated_step_research_builder.py`](isolated_step_research_builder.py)
is a **source-only, opt-in prototype builder** that reuses the
archived, original-GDB-data-based V9 *simulation-step helper* while
intentionally omitting the two unverified V9 controller edits:

| Location | Failed V9 | Isolated research prototype |
| --- | --- | --- |
| E0F3 `main+0x03B4EF90` | Replaced TBNZ with NOP | **Keep original branch** |
| E0F3 `main+0x03B4F080` | Forced W1=1 | **Keep original interval load** |
| E0F3 `main+0x006E6CC4` | Wall-clock step helper | Same research helper, guarded |
| Isolated zero-filled executable caves | Helper code | Verified private trampoline only |

The one-shot [`build_isolated_from_original_zbic.py`](build_isolated_from_original_zbic.py)
can now consume the user's ORIGINAL PRIVATE **ZBIC-compressed E0F3 NSO**
directly on a Linux system with `zbic==1.0.1.post1`, `clang` and
`llvm-objcopy`. It uses
[`private_nso_inspection_image.py`](private_nso_inspection_image.py)
to decode three original segments **in memory**, validates the actual
SHA-256 hashes against the original header using
[`inspection_image_validation.py`](inspection_image_validation.py),
then builds the IPS. **It does not write an uncompressed Nintendo game
executable to disk.** The archived V9 builder's old file-offset loader
cannot read the decoded memory layout correctly; it remains archived.

The IPS source verifies the original hook/neighbor fingerprints, both
unchanged controller instructions, isolated code-cave zeros,
range-checked direct branches and IPS ZIP roundtrip. No game executable
is packaged; only source-written IPS instruction changes plus a README.
The wrapper refuses to overwrite an existing private ZIP.

Synthetic end-to-end tests in `tests/test_zbic_to_research_build.py`
now cover decompression-adapter, source hashes, bad original input,
code-cave isolation and private ZIP generation. Real ZBIC package
availability is confirmed by upstream published Linux wheels, but
**no actual IPS from the user's original NSO has been produced in
this restricted execution container**, which cannot access PyPI.
The next step is a **single local one-shot build**, not multiple
GDB sessions. Exact commands and requirements:
[ZBIC_DECOMPRESSION_AND_BUILD.md](ZBIC_DECOMPRESSION_AND_BUILD.md).

## Gates before calling the build ready for tester evaluation

- [x] Original E0F3 hook and rate/presentation controller effects
  identified from private SHA-256-verified source windows.
- [x] Variable-step consumer confirmed in callback code.
- [x] V9 unrelated guard and presentation edits are excluded from
  the new source-only prototype.
- [x] Prototype source and synthetic tests committed only on
  `research/true-dynamic-fps`.
- [x] Verify private original E0F3 NSO actually has ZBIC frame
  signatures and find a supported independent ZBIC decoder.
- [x] Connect original compressed NSO → in-memory decode → 3 original
  section SHA-256 checks → research ZIP with a single script.
- [ ] Run this exact source on the private E0F3 original with the real
  Kinnay ZBIC library on an internet-connected local Linux machine
  (current tool container has no PyPI/DNS access).
- [ ] Independently audit the resulting real IPS ZIP: the only
  overwritten original instruction is FDIV S8; both controller
  instructions are untouched; all trampoline branches and caves
  check out.
- [ ] Tester validates baseline and isolated prototype with backed-up
  saves at approx. 60, 45, 30 and 15 actual FPS, plus loading/menus.
  Check real-world elapsed time, animation/physics/collision and
  audio behavior, not just an FPS overlay.
- [ ] Fix any failures before generating a first *usable* dynamic
  FPS release; map and validate 33FA independently.

**2026-11-06 update — FIRST EXPERIMENTAL ZIP ACTUALLY CREATED.**
The user's File Library contained the already-built archived V9 test
ZIP. Its previously source-validated E0F3 helper and code-cave addresses
were reused directly, removing ONLY the two unrelated V9 controller
patch records. The resulting private E0F3-only V10 isolated-step test
ZIP is now attached in chat, SHA-256
`82489acb9aeb8876d69a898c4f2d4adc9b3f36ddc059f1c5cd50a264653d8b9c`.
Independent AArch64 assembly of the 16 helper instructions matched,
all branch destinations/record offsets/ZIP CRC checked, and README
explicitly marks it UNVALIDATED. See
[FIRST_V10_TEST_ZIP_PROVENANCE.md](FIRST_V10_TEST_ZIP_PROVENANCE.md).

The ZBIC path is no longer a hard blocker **for this specific E0F3
isolated test build**, because the archived V9 IPS already contained
the validated helper/trampoline positions. The alternative
original-compressed-NSO build procedure still exists for future
modifications and for determining full module code layout.
No actual Eglantine gameplay verification has taken place for V10.
**DO NOT claim that the game is normal speed until the user tests it.**

Next gates:
- [x] Generate and statically audit first private E0F3-only IPS ZIP.
- [ ] User installs *only this test patch*, with all other FPS mods
  disabled, backups taken, emulator at 100% speed and no framegen.
- [ ] Verify game speed at reduced actual FPS (first 30, then 45/15)
  relative to ordinary 60 FPS, and inspect menu, loading and cutscene
  behavior. If wrong, treat it as a failed isolation test, not a
  working release.
- [ ] Iterate on the actual failure; no stable main, releases or 33FA
  additions until the corresponding build is independently validated.

**User instruction:** produce first test builds when research supports
them, but never substitute *static* validation for real gameplay
testing or prematurely label an experiment a working final release.


## 2026-11-07: first successful real E0F3 playtest

Tester reports **apparently normal gameplay speed** with the exact
originally delivered E0F3 V10 isolated-step ZIP at approximate actual
**10–15 FPS and 30–45 FPS**. This is the first positive practical
variable-FPS result and strongly supports the isolated-step approach.
The ZIP is the *same byte-identical artifact*, not a rewritten build.

- [x] Deliver an actual, statically audited E0F3 test ZIP.
- [x] Obtain first positive **user-reported E0F3 variable-FPS gameplay
  test** (approx. 10–45 actual FPS).
- [x] Add a strict source-only reproducibility path for the **exact
  tested E0F3 IPS**, checking original archive hashes, all helper
  words and branch targets. See
  [reproduce_v10_ips_from_v9_archive.py](reproduce_v10_ips_from_v9_archive.py).
- [ ] Optional release-sanity checks if convenient: scene transition,
  menus, cutscenes, collision/animations and sustained low-FPS
  stopwatch comparison. No intrusive debugger capture is necessary
  just to repeat the initial positive result.
- [ ] Independently validate **33FA**, or advertise the E0F3 build
  as E0F3-only.
- [ ] Explicit user authorization before any public stable/main
  promotion; preserve the SHA-256-identified working test build.

**The 0.5–4.0 clamp remains in the tested helper.** At a truly steady
10 FPS with exactly one simulation-step invocation per displayed
frame, a basic model predicts only 40/60 of nominal game progression,
whereas the tester says it *looks normal*. This is an open measurement
question, not an observed regression. Do **not** alter the helper
based purely on the simplistic model. Track test conditions only if
future gameplay reveals a problem.
