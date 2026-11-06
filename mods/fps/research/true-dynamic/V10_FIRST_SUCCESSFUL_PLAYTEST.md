# E0F3 isolated-step V10 — first successful user gameplay report

Date recorded: **2026-11-07**. Research branch only.

## Test outcome

The tester installed and ran the first E0F3-only
`OOT_Remake_True_Dynamic_FPS_Isolated_Step_E0F3_V10_TEST.zip`
(SHA-256:
`82489acb9aeb8876d69a898c4f2d4adc9b3f36ddc059f1c5cd50a264653d8b9c`).

**Direct user report:** Game speed appears to adjust correctly and remain
normal as the *actual* rendering frame rate changes. The tester
specifically reported normal gameplay speed around **10–15 FPS** and
**30–45 FPS**, describing the result as a complete success. This is the
first real positive gameplay result for a genuinely dynamic-step
prototype, in sharp contrast to the failed V9 combined patch, which
had sped up markedly around 30 FPS.

**Evidence class: user-reported live qualitative playtest**. The
assistant has not independently run Eglantine, timed gameplay with a
stopwatch/video, measured collision/physics accuracy, stress-tested
gameplay loads/cutscenes, or tested the 33FA base build. Do **not**
mislabel this as formal objective speed/physics validation across
all scenes. Conversely, do not ignore or downplay the user-observed
success: it directly tests the practical goal and is a major project
milestone.

## Supported interpretation

V10 kept V9's authored elapsed-tick step helper and original frame-step
hook but **removed** only V9's two controller edits:
- Original E0F3 guard `main+0x03B4EF90` remains active.
- Original E0F3 presentation-argument load `main+0x03B4F080`
  remains active.
- Original `FDIV S8` at `main+0x006E6CC4` is replaced by the
  audited elapsed-time step helper.

An earlier source audit showed V9's controller edits could force
contradictory native timing settings. **The V10 live success is
consistent with those removed edits contributing to V9's failure**,
but does not prove that either single edit individually caused it.
They were removed as a pair. It is no longer justified to describe
the unchanged elapsed-step helper as definitively defective just
because combined V9 failed.

There is one known design boundary: the helper clamps step to a maximum
of **4 nominal simulation units per invocation**. If it executes exactly
once per *actual* rendered frame at a steady **10 FPS**, simple
accounting yields only **40 nominal units/second** rather than 60.
However, the tester says normal speed also appears around 10–15 FPS.
This indicates that interpreting overlay FPS as exact step-callback
frequency may be invalid in that situation, or perception / scene
conditions may matter. **Do not contradict the actual live report with
that simplified model; do not promise universally perfect sub-15 FPS
behavior based solely on subjective observation either.** A long,
repeatable real-time comparison may clarify this *if needed*, not
before routine stabilization.

## What remains for a stable release

The **working test ZIP is frozen**. Avoid blindly optimizing,
changing clamp constants, moving code caves, or refactoring
guest instructions while the user is seeing success.

High-value hardening work is **non-invasive**:
1. Make exact IPS reproducible without depending on interactive
   reverse-engineering. The source-only
   [`reproduce_v10_ips_from_v9_archive.py`](reproduce_v10_ips_from_v9_archive.py)
   now requires the original private V9 ZIP SHA-256, original
   E0F3 IPS SHA-256, exact 22-record offset set, independently
   assembled 16 helper opcodes, and all 4 branch targets.
   It removes exactly two controller records and verifies the final
   209-byte IPS SHA-256 is
   `306e36cec3efc28a38df627ed38245fe29008855a85cfe4a249a7d8fb2fd1365`.
   Synthetic tests are in
   `tests/test_reproduce_v10_ips_from_v9_archive.py`.
2. Preserve the already playtested ZIP as a golden reference and
   test it by SHA, without repackaging/relabeling a different binary
   under the same name.
3. Optional targeted validation, not another broad diagnostic cycle:
   menu/cutscene/load/transition behavior and a brief sustained
   stopwatch comparison below 15 FPS, if convenient. Do not
   demand extensive retesting from the user just to move documents.
4. The **33FA base build is not included**; its native function
   layout/callbacks still need independent static and playtest
   validation before declaring both builds supported.

## Release policy

Current status: **E0F3 FIRST SUCCESSFUL LIVE PLAYTEST**.
It is appropriate to consider a release candidate after routine
sanity checks, but **not to silently push a stable/main release**
or claim all-game/full-build support without permission and evidence.
The private archive contains only an IPS, a README, and an audit
manifest. No Nintendo game instructions or full executable appear
in the repository.
