# Developer / AI handoff — Ocarina of Time true dynamic FPS

> **Read this first if continuing the project in a new chat, with another AI,
> or with a different developer.** This file is intended to stand alone.
> Status: **NOT SOLVED**; last playable experiment **V9 FAILED**.
> Latest runtime milestone: six E0F3 unmodified-game numeric snapshots at ~30 FPS show the frame-context +0xD50 integer counter and +0xD58 double accumulator equal at all six points and rising together by 591 units over five requested 4-second free-running intervals (~29.55 per requested running second). Timing configuration remains step=1.0, nominal rate=60 throughout. This supports why original gameplay slows below 60 FPS, but does not yet count actual physics calls or solve failed V9.
> Updated **2026-11-06**. Keep working on branch
> `research/true-dynamic-fps`; never overwrite or merge `main` without
> deliberate review and gameplay evidence.

## 1. Project and goal

- Repository: <https://github.com/TheCraZyDuDee/Ocarina-of-Time-Remake-Mods>
- Development branch: <https://github.com/TheCraZyDuDee/Ocarina-of-Time-Remake-Mods/tree/research/true-dynamic-fps>
- Working release code is on **`main`** under `mods/fps`; its released ZIPs
  are in `releases/`. Keep both untouched during research.
- Game: *The Legend of Zelda: Ocarina of Time Remake* (Nintendo Switch 2);
  title ID **`0400486024DEC000`**.
- Supported **main** executable build IDs:
  - Updated (E0F3): `E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348`.
  - Base (33FA): `33FA6C2C23848282A77E8B88A0A93F4887C55920`.
- Goal: presentation may vary with GPU/CPU performance while **menus,
  physics, movement, animations and game clocks retain real-time speed**.
  In particular do not accelerate at 30–60 FPS or slow during drops.
  The user would ideally like every nonzero FPS, but low FPS may exceed
  an engine's ability to catch up. At literally **0 displayed FPS**, a
  render-driven simulation cannot progress unless updates run separately.

The user tests on Lichii/Eglantine/Orchid-derived Switch 2 emulators.
Performance can vary badly, so compare **game speed against real elapsed
seconds and repeatable movement**, not just the FPS overlay.

## 2. Verified results and failures (historical)

| Candidate | What the user reported | Conclusion |
| --- | --- | --- |
| Fixed 30 FPS (existing main release) | Normal gameplay speed on updated E0F3 build | Working reference; base version only static-checked |
| Native adaptive (existing main release) | 20 FPS played well | Working native discrete-mode option; 30/60 not independently verified |
| Variable-average mod (existing main release) | Not gameplay-tested | Alternates native 20/30/60 frame intervals; not the desired fully dynamic system |
| Fixed 15 FPS timing probe | Seems normal near 15 FPS | Four simulation ticks/frame can work *when presentation actually is 15 FPS* |
| Fixed 10 FPS timing probe | Still rendered around 15 FPS; overly fast | Six ticks/frame × 15 FPS ≈ 150% game speed |
| Fixed 5 FPS timing probe | Still rendered around 15 FPS; much faster | Twelve ticks/frame × 15 FPS ≈ 300% game speed |
| V7 measured-time patch | Menus work; loading a save leads to black screen and 0 FPS | Failed; precise cause **unknown** |
| V8A uncapped-presentation probe | Loads saves; menus at ~60 FPS too fast, gameplay at ~30 FPS too fast | Uncapping render presentation without fixing game time causes speed mismatch |
| **V9 real-elapsed probe** | Near 15 FPS feels normal; around 30 FPS very fast; below 15 slow | **Failed**. Consistent with its upper 4-tick clamp being saturated, but saturation **not measured** |

**DO NOT use V7/V8A/V9 in normal gameplay.** V9's local builder
`real_elapsed_probe_builder.py` is intentionally guarded by a
`--reproduce-known-bad-v9` research override. Its prior success in CI
established only byte/algorithm checks, *never actual game timing*.

## 3. Critical binary findings

The following module-relative offsets were statically verified on *original
decompressed* NSOs; no game binary is committed.

| Purpose | E0F3 (main+) | 33FA (main+) |
| --- | --- | --- |
| Interval-driven controller | `0x03B4EF60` | `0x03AF18F0` |
| FPS-target controller | `0x004DBDA0` | `0x0045DA10` |
| Shared FPS setter | `0x004DC0F0` | `0x0045DD60` |
| Interval presentation argument | `0x03B4F080` | `0x03AF1A10` |
| **Simulation-step divide** | **`0x006E6CC4`** | **`0x006B5A08`** |
| FPS load in frame-step function | `0x006E6C98` | `0x006B59C8` |
| 60/30 rate selection before divide | `0x006E6CC0` | `0x006B5A04` |

The original frame-step path (actual instructions verified in **both** builds):
- `x8 = [frame_context + 0xA8]`,
  `x21 = [x8 + 0x20]` (FPS state object).
- The `LDR S0,[X21,#0x2C8]` instruction loads raw bits `0x0000003c` (integer 60, not a float32 encoding). A subsequent **`SCVTF S0,S0` at E0F3 `main+0x006E6CA8`** numerically converts that 32-bit integer to floating-point 60.0. This directly reconciles the old raw-field reading with live `s0=60.0` in 12/12 gameplay samples. The field is now a confirmed integer input for this E0F3 frame-step expression; do not extrapolate its broader lifetime or identical instruction location to uninspected 33FA code.
- `s1` is selected as **60.0 or 30.0**, based on a state flag.
- `fdiv s8,s1,s0` is the exact original instruction; **the live gameplay values are s0=60.0 and s1=60.0 (12/12), so the immediate divide result is 1.0**. Do not treat surrounding loads as proof of a simulation-step formula in every path.
- `s8` is subsequently used by the frame-update machinery; its exact
  effects on all physics/animations must still be verified.

A **separate** FPS controller (and the native interval controller) reads
a pair of 64-bit timing samples from an object at `+0x148` and
`+0x150`, converts ticks using a shared frequency helper
(E0F3 `main+0x00E3A5C0`), estimates an FPS and calls the **same FPS
setter**. This is not proof of a usable full-frame wall-clock delta.
The FPS setter normally accepts integer rates dividing 60 and suggests
a lower rate otherwise. An alternate 40+ FPS branch is guarded by two
object flags whose meaning and activation are **not confirmed**.

**Crucial V9 error:** its helper followed
`[frame_context+0xA8] -> [+0x20] -> [+0x100]`, loaded that 64-bit
field as if it were **latest elapsed frame ticks**, and calculated
`clamp(base_rate * value / CNTFRQ_EL0, 0.5, 4.0)`. No write-site
or runtime trace established what `FPS_state+0x100` really contains.
If it contains a cumulative value or uses another unit, V9 would stay
clamped at 4 ticks, implying speed of ~100%/200%/400% at 15/30/60 FPS
for a 60-Hz simulation. This is a **hypothesis**, not a captured trace.

The game itself does **not** contain inline `MRS CNTPCT_EL0` or
`MRS CNTVCT_EL0` in its original text (a static scan of both
decompressed NSOs found none). It likely accesses clock services
through functions instead. This does **not** prove there is no reliable
timer elsewhere in the game.

## 4. Emulator research and why MKW differs

See the upstream Lichii implementation:
- Game-specific MKW patch:
  <https://github.com/zortos293/Lichii/blob/main/src/core/loader/nso.cpp>.
- Present pacer:
  <https://github.com/zortos293/Lichii/blob/main/src/core/hle/service/nx2_gsv.h>.
- The MKW patch selects a native dynamic mode **and** replaces its
  partial frame-timing measurement with whole-frame time. The emulator
  sets presentation interval 1 **only for that confirmed game mode**.

Lichii's general present pacer clamps the requested interval to **1–4**,
unless explicitly forced, so increasing native simulation ticks to 6
or 12 did not lower the user's observed presentation beyond ~15 FPS.
The guest Switch 2 counter is configured at **31.25 MHz**.

**Do not transplant** MKW's offsets, object paths, or mode values to
Ocarina. V8A demonstrates why decoupling presentation alone breaks speed.
The MKW approach is useful only as a game-specific design precedent.

## 5. Repo navigation / runnable research

All the following files are on `research/true-dynamic-fps`, under
`mods/fps/research/true-dynamic/`:

- `README.md` — research overview / current status.
- `INVESTIGATION.md` — early controller findings, MKW comparison.
- `TWO_CONTROLLERS.md` — controller offsets and setter/branch checks.
- `V9_FAILURE.md` — latest actual gameplay failure and saturation hypothesis.
- **`HANDOFF.md`** — this document; resume here.
- `timing_model.py` — offline bounded fixed-60-Hz accumulator model.
- `frame_rate_acceptance.py` — rate setter acceptance model.
- `map_time_managers.py` — read-only static mapping of both controllers.
- `inspect_controller.py` — original timing-opcode verification.
- `inspect_frame_step.py` — read-only verification of the **exact**
  original frame-step expression for both build IDs.
- `v9_failure_model.py` — V9 four-tick saturation arithmetic.
- `real_elapsed_probe_builder.py` — failed V9 builder,
  **blocked by default**; retain for forensic comparison only.

Regression tests in repo root `tests/` cover arithmetic, controller
mapping, and offline failure cases. They use Python stdlib only.
From a checkout of the research branch:

```sh
git checkout research/true-dynamic-fps
python3 -m unittest discover -s tests -v
python3 mods/fps/research/true-dynamic/inspect_frame_step.py /PRIVATE/E0F3_decompressed.nso
python3 mods/fps/research/true-dynamic/inspect_frame_step.py /PRIVATE/33FA_decompressed.nso
```

**Those NSOs must be the user's own original decrypted, decompressed
executables**, not modified by prior FPS patches. The static inspector
checks all three NSO segment SHA-256 hashes before reporting opcode
matches. For *any* new patch, fail closed on unknown or modified builds.

The available earlier local research paths included
`/mnt/data/main1_decompressed.nso` (E0F3) and
`/mnt/data/main_decompressed.nso` (33FA), but **do not assume they
persist across chat sessions or AI environments**. They must never be
committed or sent to public services. If absent, ask the user to
provide their legally obtained private executables again.

## New: original-NSO compression and reproducible private inspection

The two original private uploads currently available as filenames \`main\`
and \`main(1)\` are **not LZ4**. Their header flag word is \`0xFF\`,
including \`NsoFlags_UseZbicCompression\` (bit 7), and all three
compressed segment streams start with **\`ZBIC\`**. The matching build IDs are:

- \`main\`: **33FA** base build;
- \`main(1)\`: **E0F3** updated build.

**A normal LZ4 decompression attempt fails**, as expected. Nintendo's
ZBIC is a modified Zstandard format introduced in system 22.0.0.
The original segments' SHA-256 values and decompressed text/rodata/data
sizes are available in their NSO headers. See [Eden ZBIC support](https://git.eden-emu.dev/eden-emu/eden/pulls/4482)
and [the independent ZBIC Python project](https://github.com/kinnay/zbic).

A [new independently authored private inspection-image helper](private_nso_inspection_image.py)
handles plain/LZ4/ZBIC compressed NSOs. The ZBIC package is **optional,
external and separately GPL-licensed**; this MIT repository does not
include or copy its implementation. The helper preserves the original
NSO header, validates each of its three SHA-256 segment digests, and lays
out the segments at \`0x100 + module_memory_offset\` for the existing
read-only opcode inspectors. **The output is not a bootable NSO.**

The helper and [synthetic tests](../../../../tests/test_private_nso_inspection_image.py)
pass; however, **we did not perform real ZBIC decompression in the
current runtime**, because that external decoder was not installed and
this runtime cannot obtain a package from the network. The old
decompressed paths listed elsewhere in this handoff are not currently
present. Do not claim to have reverified binary offsets in this
session from the compressed files.

When ZBIC is available **in your own private environment**, run:

\`\`\`bash
python3 -m pip install zbic
python3 mods/fps/research/true-dynamic/private_nso_inspection_image.py \
  "/private/path/main" "/private/path/33FA_private_inspection.nso"
python3 mods/fps/research/true-dynamic/private_nso_inspection_image.py \
  "/private/path/main(1)" "/private/path/E0F3_private_inspection.nso"
python3 mods/fps/research/true-dynamic/inspect_frame_step.py \
  "/private/path/33FA_private_inspection.nso"
python3 mods/fps/research/true-dynamic/inspect_frame_step.py \
  "/private/path/E0F3_private_inspection.nso"
\`\`\`

**Never run this conversion in a CI job or upload the source or output
NSO to public GitHub.** The helper is deliberately inspection-only,
refuses overwrite, and prints no proprietary bytes or keys.

## 6. Remaining technical blocker and recommended next method

**Find a real, monotonic elapsed-frame-time source with validated
provenance.** No such in-game field is confirmed today.

A successor should:

1. Identify where the FPS state `+0x100` field is written and its units.
   Do not guess from nearby offsets, names, or compiler layout.
2. Use **non-invasive guest debugging or an emulator-side trace** at
   `main+0x006E6CC4` (E0F3) / `main+0x006B5A08` (33FA)
   to record actual live `s0`/`s1`/`s8`, the supposed time sample,
   and **actual present timestamps** during menus, save loading,
   and gameplay at ~15/30/45/60 FPS. Verify whether the frame-step
   function is called once per rendered frame.
3. Correlate timing samples to monotonic wall-clock elapsed time.
   Distinguish CPU execution time, GPU fence time, vblank delay,
   average target interval, and cumulative tick counters.
4. If using consecutive `CNTPCT_EL0` snapshots instead, prove a
   **writable, per-instance, safely initialized previous-timestamp
   location** and scene-transition reset. Never write code-cave text
   pages or repurpose unverified game-state fields as storage.
5. Keep presentation and simulation coordinated. A single
   `base_rate / target_fps` replacement cannot prove all subsystems
   remain correctly synchronized. Physical substep limits and
   object update loops must be inspected, not guessed.
6. Before testing, statically verify all branches, stack/register
   preservation, game segment hashes, both build IDs, all code caves,
   game mode transitions, and no excluded ROM/game assets in ZIP.
7. Keep any new **experimental ZIP off the public repo** until the
   user confirms it reaches gameplay, menus/timers are correct,
   physics is sane, and speed remains normal at different FPS.

For 60 Hz, a genuine wall-clock frame delta would be approximately
`1/15 = 66.7 ms`, `1/30 = 33.3 ms`, or `1/60 = 16.7 ms`.
Guest counter readings at 31.25 MHz for these intervals are roughly
2.08m, 1.04m and 0.52m ticks. **An observed value outside that
order of magnitude is a warning, not input to blindly clamp.**

Also inspect whether the game can execute multiple fixed physics
updates independently of drawing, especially at low FPS; changing
one float is not equivalent to fixed-step simulation. At severe
frame drops a CPU-bound emulator may be unable to keep up at all.

## 7. Publication, licensing and safety

- GitHub's default `main` branch is the **stable published mods** branch;
  preserve it and `releases/` unchanged until tests succeed.
- Only source, original small instruction/IPS metadata, notes and
  tests belong on research branch.
- The repo license is MIT for our independently authored source;
  **do not copy GPL emulator code into MIT mod code**. Link to
  third-party source for architectural reference and attribution.
- Never publish Nintendo game binaries, NSOs, keys, saves, crash logs
  containing personal data, or copyrighted assets.
- ZIPs should contain only small `IPS32` patches targeting the exact
  build IDs, plus instructions, and must not combine incompatible FPS
  mods. They are built privately from the user's own dumps.
- Don't say that a static opcode check or mathematical test proves
  gameplay timing. It does not.
- Do not delete prior failed research: it documents known traps.

## 8. Ready-to-paste prompt for a new AI

> Continue development of a true variable-FPS mod for the Nintendo
> Switch 2 Ocarina of Time Remake using the GitHub repo
> `TheCraZyDuDee/Ocarina-of-Time-Remake-Mods` and the branch
> `research/true-dynamic-fps`. **First read**
> `mods/fps/research/true-dynamic/HANDOFF.md`,
> `V9_FAILURE.md`, `TWO_CONTROLLERS.md` and the source/test files.
> Do not touch stable `main` or push experimental ZIPs.
> V7 black-screened after loading a save; V8A sped up gameplay;
> V9 again sped up above ~15 FPS because its timing input is not
> verified. Both E0F3 and 33FA builds must be supported. Advance
> only with source-derived evidence and runtime timing validation;
> preserve every research finding in the branch for future handoff.

## 9. Runtime timing diagnostic prepared (2026-11-06)

A new **non-installable, read-only GDB-stub probe** provides the first
direct approach to observing V9's suspect input. See
[\`GUEST_TIMER_TRACE.md\`](GUEST_TIMER_TRACE.md), together with
[\`guest_timer_probe.py\`](guest_timer_probe.py).

It uses the existing guest debugger in compatible Lichii/Eglantine builds,
rather than injecting another risky IPS. It temporarily breaks at the
original simulation division (\`main+0x006E6CC4\` E0F3 or
\`main+0x006B5A08\` 33FA), confirms the original instruction,
samples \`FPS_state+0x100\`, \`+0x148\`, \`+0x150\` as 64-bit values and
\`+0x2C8\` as **raw bits** (no assumed type), then restores the breakpoint and
resumes the game. Source contains no private game data, executable
copies or emulator GPL code.

There are two levels of validation: mocked GDB unit tests and a local
fake debugger integration test verifying attach/step/resume. **It
has not been tested against live emulator process timing.**
Sampling necessarily pauses frames, so samples are suitable for *field
provenance clues* but not for unbiased frame duration measurements.

Next step when a tester can run a compatible GDB-enabled emulator:
capture **12 samples from menu and gameplay** with all other FPS
patches disabled, inspect whether \`+0x100\` is an absolute tick count,
a stable field, or an actual delta. Then trace the **write-site** for
any candidate value and re-check its units and lifecycle. Do **not**
build V10 just because the trace shows a plausible number.

The script can be downloaded independently for debugging; it is
**not a new FPS mod and should not be placed in releases/**.

## 10. Eglantine debugger mismatch (2026-11-06)

The tester ran `guest_timer_probe.py` on CachyOS / Eglantine. The
guest debugger **connected successfully** on port 6543; the script
resumed the game and accepted Enter to sample menus. It then stopped
safely at the **original hook verification**:
`ValueError: Timing hook is not original`. This does *not* prove that
any FPS mods were enabled. The previously supplied log documented
E0F3 `main` loaded at `0x80e26000` **in a session that later shut down**.
Reusing that base in a later session is unverified; it may be a stale
guest virtual address.

The updated `guest_timer_probe.py` now provides `--check-hook`
to print the precise observed AArch64 instruction at the computed
hook site, **without setting any breakpoint**. It also makes a
mismatch exception print the observed instruction and address. The
diagnostic itself resumes the game after the check. Synthetic unit
tests and a fake GDB-stub integration test cover this preflight.
See `GUEST_TIMER_TRACE.md` for exact Linux commands.

**Status remains unresolved** until the tester reports the read-only
preflight output or uploads a fresh current-launch `eden_log.txt`.
Do not remove the verification check or generate V10 based on this
error alone. No stable mod/release was changed.

## 11. First Eglantine menu trace completed (2026-11-06)

The tester supplied **12 consecutive GDB breakpoint samples** from menus
on E0F3 after the original-instruction guard passed. Details, aggregate
statistics and caveats are preserved in [MENU_TIMING_FIRST_TRACE.md](MENU_TIMING_FIRST_TRACE.md).

- `x21+0x100` was about **25.6–26.0 million ticks** for 11 of 12
  samples. At 31.25 MHz this is approximately 0.82–0.83 seconds,
  overwhelmingly **debugger pause overhead**, not normal gameplay timing.
- `x21+0x148` tracked `+0x100` within 209–384 ticks.
- The decrease in `x21+0x150` closely tracked the **previous**
  `+0x100` sample (correlation ~0.99996). This suggests the +0x100
  field may actually be a frame duration rather than an absolute
  counter; it still has **unverified units and write-site**.
- `x21+0x2c8` was **raw 0x3c / integer 60** in all 12 samples.
  The old script interpreted this as a tiny float 8.4e-44 and falsely
  labeled it `target_fps`. This challenges the assumed dataflow.

Corrected `guest_timer_probe.py` now captures actual AArch64
floating-point `s0`, `s1` and `s8` register inputs in addition to
raw `+0x2c8` field bits. It still uses temporary breakpoints,
so measurement distortion remains. **Completed:** a 12-sample gameplay trace confirmed both live operands are 60.0, and s8 prior to division is 0. The next step is tracing the writer of x21+0x100, not repeating a timer-read experiment.

## 12. First live gameplay FP-register trace (2026-11-06)

**Authoritative new observation:** the user supplied 12 successive
`gameplay_timing_v2.json` samples from Eglantine on E0F3 while the game
was loaded. Each registered exactly **`s0 = 60.0` and
`s1 = 60.0`** at the original `fdiv s8,s1,s0` (the pre-division
`s8` value was 0.0). Therefore the division computes **1.0** even
when the emulator runs at roughly **30 FPS / 50% game speed**.
This is strong evidence of no *direct* actual-FPS adaptation at this
site; a 30-Hz update loop with a fixed 1.0 tick would be half speed
**if the update happens once per present**. Call count and downstream
uses of `s8` are not yet captured.

Other fields:
- `x21+0x100` ≈24.94–26.71 million ticks in 11 paused-breakpoint
  samples (median 26,499,606). These ~0.8s values are dominated by
  debugger pauses; not real uninterrupted frame times.
- `x21+0x148` sometimes differs from `+0x100` by ~0.7m ticks.
- Negative signed values in `x21+0x150` decrease approximately by
  the *preceding* `+0x100` reading (r≈0.99995).
- `x21+0x2c8` raw uint32 is 60, but that is not a float32 60.
  Do not assume these bits are the direct producer of live `s0`.

Details are in
[`GAMEPLAY_TIMING_FIRST_TRACE.md`](GAMEPLAY_TIMING_FIRST_TRACE.md).
**No source/private game binaries or raw user gameplay JSON committed.**

A NEW independently authored candidate
[`guest_timer_write_trace.py`](guest_timer_write_trace.py) uses
Eglantine's documented GDB **Z2 write watchpoints** to find the
actual writer of `x21+0x100`, after identifying x21 at the verified
original frame-step. Synthetic tests are green, but the watchpoint
has **not yet run against a live emulator**. See
[`GUEST_TIMER_WRITE_TRACE_GUIDE.md`](GUEST_TIMER_WRITE_TRACE_GUIDE.md).
This is source-only diagnostics, NOT V10 or a working FPS mod.

Next: obtain four write-site hits from gameplay, verify instruction
provenance and units and distinguish real elapsed *full frame* time
from per-subsystem/partial time. Only then consider another IPS.

## 13. First live Eglantine timer writer site (2026-11-06)

The tester obtained four real GDB Z2 watchpoint hits on E0F3 at x21+0x100,
all reporting PC **main+0x0346C7EC**. Values were 7,040,467; 19,138,755;
476,073; 1,263,539. They are not monotonically increasing. At the guest
31.25 MHz clock the last two represent 15.2 and 40.4 milliseconds, provided
this field uses counter ticks. The watchpoint stop semantics and writer opcode
have not been disassembled, so this is still a candidate duration source.

Read TIMER_WRITER_FIRST_TRACE.md. An independent guest_writer_static_window.py
helper captures 640 bytes around the writer PC at initial debugger halt,
verifies original frame-step code and resumes execution without breakpoints.
The produced JSON is PRIVATE and contains original code words; do not publish
it or the proprietary binaries. Analyze it privately before designing V10.

## 14. Timer import trampoline reached (2026-11-06)

The 160-word private writer code window proved
`main+0x0346C7EC` is `str x8,[x19,#0x100]` on E0F3, preceded by
`x8 = current_timer_read() - [x19+0x108]` and followed by a refresh
of `[x19+0x108]`. The write is conditional; neither a whole-frame
measurement nor exact units are established.

The subsequent private `timer_source_window.json` (96 words, SHA-256
verified) shows the presumed timer routine at `main+0x03C41FD0` is
actually an **AArch64 import trampoline**. Its first entry reads a
function pointer at **`main+0x04CBF1B0`** and branches through it.
We have not yet identified the target function or its clock semantics.

See [`TIMER_WRITER_STATIC_ANALYSIS.md`](TIMER_WRITER_STATIC_ANALYSIS.md).
The new [`guest_timer_import_target.py`](guest_timer_import_target.py)
resumes an initially stopped GDB guest, waits for a menu/gameplay scene,
interrupts it once, verifies known original opcodes and the pointer slot,
then privately captures a bounded 256-byte target-code window if mapped.
Tests are synthetic only; no live capture yet. User should supply the
private `timer_import_target.json`, **not commit it**. Keep stable
releases untouched and do not produce V10 until units, frame scope,
and actual simulation update cadence are verified.

## 14. Timer import resolved: physical counter identified (2026-11-06)

**New direct evidence; not yet a working dynamic FPS mod.** The tester ran
`guest_timer_import_target.py` after loading gameplay on E0F3. Its private
256-byte capture passed SHA-256 validation. The original import stub at
`main+0x03C41FD0` obtains an out-of-main function pointer through
`main+0x04CBF1B0`. At the resolved function, the first instruction is
**`MRS X0, CNTPCT_EL0`**, immediately followed by `RET`.
A nearby clock-frequency helper returns **31,250,000** (`0x01DCD650`),
consistent with the Switch 2 guest's physical counter rate.

Combined with the private original writer window, the `+0x100` producer
computes a **difference of physical-counter readings**:
at `main+0x0346C7E0` it calls the clock, subtracts the saved
`[X19+0x108]` reading, stores the delta to `[X19+0x100]` at
`main+0x0346C7EC`, then calls the clock again and refreshes
`[X19+0x108]` at `main+0x0346C7F4`. The writer is conditional and
there is a separate partial-duration field at `+0x148`.
The watchpoint on `X21+0x100` hitting this writer links those two
views during that gameplay capture.

**Crucial distinction:** timer *provenance and likely units* are now
established, but the field is not yet proven to contain the **complete
elapsed time per presented frame**, nor to refresh before each frame-step
`fdiv`. V9's real gameplay failure is unchanged; no new IPS is justified.
The former observation that no `MRS CNTPCT_EL0` appeared in original
**main** text does not contradict an import through a separate module.

See [COUNTER_SOURCE_CONFIRMED.md](COUNTER_SOURCE_CONFIRMED.md).
Next: capture cached durations at intervals of **uninterrupted gameplay**
using a sparse read-only debugger snapshot (not writer watchpoints), while
cross-checking actual FPS independently. Do not publish private code windows
or resolved guest addresses. Base 33FA target remains unmapped.

The next opt-in read-only probe is [`guest_timer_quiet_snapshot.py`](guest_timer_quiet_snapshot.py),
with synthetic tests in `tests/test_guest_timer_quiet_snapshot.py`.
It temporarily locates `X21` at the original `fdiv`, removes its breakpoint,
then lets the game run for several seconds between brief debugger interrupts
and reads only numeric fields `+0x100`, `+0x108`, `+0x148`, `+0x150`.
It has NOT yet been run live; the observations are sparse cached values,
not an unbiased FPS profiler. See the commands in
[COUNTER_SOURCE_CONFIRMED.md](COUNTER_SOURCE_CONFIRMED.md).


## 15. First sparse uninterrupted gameplay timer sampling (2026-11-06)

The tester ran the new read-only `guest_timer_quiet_snapshot.py` during
E0F3 gameplay at approximately **50 displayed FPS**, taking five snapshots
after four-second intervals of resumed gameplay. The `+0x100` cached
physical-counter differences were **625,074–720,094 ticks**, equivalent
to **20.002–23.043 ms** at 31.25 MHz (mean 22.106 ms); the equivalent
per-sample rates, **43.4–50.0 FPS**, are consistent with the reported
FPS overlay. The separate `+0x148` field was always shorter,
**17.342–20.713 ms**, and the saved `+0x108` timestamp advanced by
**4.158–4.171 seconds** per approximately four-second debugger cycle.

All five unmodified-game values are *below* V9's four-tick cap threshold
of **2,083,333 ticks** at nominal 60 Hz. If V9 consumed these values
correctly, they would imply approximately 1.20–1.38 ticks, **not 4.0**.
This makes the previous theory that the input is always a cumulative
counter or universally saturates the clamp **untenable as a general
explanation**. It does **not** establish the cause of V9's failure:
under V9, in menus, after loading or at lower FPS the same field may
have different timing or freshness. An approximate overlay reading and
five paused snapshots are not proof of whole-frame cadence.

See [QUIET_GAMEPLAY_FIRST_TRACE.md](QUIET_GAMEPLAY_FIRST_TRACE.md).
**Next:** reuse the existing `guest_timer_quiet_snapshot.py` for a
naturally slower, stable gameplay scene (~30 FPS if available), all FPS
patches disabled and emulator speed unchanged. Do not force a different
emulator speed to simulate a slow renderer. Independently verify that
`+0x100` updates before every simulation `fdiv` and that its
consumers advance all physics once per presented frame. There is still
**no validated V10 patch**, and the 33FA writer path is unmapped.


## 16. Second ordinary-gameplay clock test: around 30 FPS (2026-11-06)

The tester supplied `quiet_timer_snapshots_30fps.json`, with **five** E0F3
cached-field snapshots separated by four seconds of resumed gameplay,
while the FPS overlay read approximately **30 FPS**. The verified
`CNTPCT_EL0`-derived `X21+0x100` field ranged **983,403–1,101,034 ticks**,
or **31.469–35.233 ms** at 31.25 MHz, mean **33.450 ms**.
The nominal 30 FPS period is 33.333 ms. The same field previously
averaged **22.106 ms** in an about-50 FPS gameplay scene, giving
clear FPS-dependent scaling across two independent workloads.

The separate `+0x148` cached field stayed shorter, **19.275–20.498 ms**
(mean 19.791 ms) instead of following the ~33 ms full-period candidate.
The `+0x108` saved counter advanced by about **4.145–4.175 seconds**
between captures, including debugger overhead. None of the five 30 FPS
samples hit V9's four-tick cap threshold of 2,083,333 ticks.
If read fresh in V9, these unpatched game timer values would yield
**1.888–2.114 nominal 60-Hz simulation ticks**, close to 2.0, not 4.0.
The previous universal 'absolute timestamp / always saturated' theory
is therefore inconsistent with these *unmodified* gameplay runs,
but V9's observed speed-up is NOT explained or fixed by these tests.

**Next is no longer another timer snapshot.** Map the actual producer/consumer
flow and update scheduling around E0F3 `fdiv s8,s1,s0` at
`main+0x006E6CC4`. The newly authored read-only tool
[`guest_frame_step_static_window.py`](guest_frame_step_static_window.py)
captures a bounded 1,024-byte original-code excerpt, verifies seven
original opcode fingerprints, never sets breakpoints, and resumes the
guest. Five synthetic tests were added; isolated local capture checks passed,
but the new repository tests have not been run in full CI and the tool
has not run live.
See [FRAME_STEP_WINDOW_GUIDE.md](FRAME_STEP_WINDOW_GUIDE.md)
and [QUIET_GAMEPLAY_30FPS_TRACE.md](QUIET_GAMEPLAY_30FPS_TRACE.md).
**Private code JSON must NOT be committed or published.** V9 is still
failed, no validated V10 exists, and 33FA still needs mapping.


## 17. First static frame-step downstream consumers identified (2026-11-06)

The tester supplied a **private, SHA-256-verified 1,024-byte E0F3 code
window** spanning `main+0x006E6BE0` to `main+0x006E6FDC`.
Disassembly establishes that `LDR S0,[X21,#0x2C8]` at
`main+0x006E6C98` is followed by **`SCVTF S0,S0` at
`main+0x006E6CA8`**. This resolves the earlier apparent conflict
between raw integer 60 (`0x0000003c`) and live denominator
`S0=60.0`. The selected numerator (60 or 30) is divided by the
converted integer target at `main+0x006E6CC4` to produce `S8`.

On a **conditional** path, `S8` is converted to double and added
to the accumulator at `frame_context+0xD58`, with an associated
atomic counter at `+0xD50`. The original code also executes
`FMOV S0,S8` at `main+0x006E6DCC`, then calls
**`main+0x03B4E300`** at `main+0x006E6DD8` with `X0` sourced
from a previously loaded global pointer. Other flag-controlled
branches bypass or reorder this path; the callee's role and full
simulation update call count remain **unverified**.

The user's baseline statement is explicit and should **not be asked
again**: with **no dynamic FPS mod**, the game **runs in slow motion
whenever actual rendering falls below 60 FPS**. The whole purpose is
normal *real-time* simulation despite reduced displayed FPS. The V9
patch caused the opposite failure, excessive game speed around 30 FPS.

See [FRAME_STEP_CONSUMERS_FIRST_TRACE.md](FRAME_STEP_CONSUMERS_FIRST_TRACE.md).
The new [guest_frame_step_followup.py](guest_frame_step_followup.py)
reads two short original-code windows around the direct downstream
callee `main+0x03B4E300` and the remaining part of the calling
function, *only after verifying original E0F3 fingerprints*.
Source-only synthetic tests are under
`tests/test_guest_frame_step_followup.py`; current live Eglantine
validation is pending. **Capture is private Nintendo code: never
publish the JSON.** See the guide in the trace note.

No V10 is validated, do not touch published main/releases or publish a
new ZIP, and no cross-build claim for 33FA follows from this capture.


## 18. Time-step converts back to nominal FPS; two caller sites (2026-11-06)

The tester privately supplied `frame_step_followup.json` for E0F3,
containing SHA-256-verified static original game-code windows at
`main+0x03B4E300` (384 instructions) and `main+0x006E6FE0`
(448 instructions). The downstream function at `main+0x03B4E300`
is a **timing-configuration converter**, not direct proof that a
variable number of physics steps executes. It receives the caller's
`S8` through `S0`, writes **`config+0x10 = step`** and
**`config+0x14 = 1/step`**, updates another scaled float at `+0x18`,
and stores a rounded integer **`60/step`** at `config+0x1C`.
For positive steps, 1 -> 60, 2 -> 30, 3 -> 20, 4 -> 15; fractional
steps may produce intermediate nominal rates. It recalculates many
other related config floats and may call a virtual callback.
The values accepted by actual downstream gameplay/physics code
are **not established**.

The **same callee is called at both `main+0x006E6DD8` and
`main+0x006E70F8`** through flag-controlled control flow.
The two paths also add `S8` to a double counter at
`frame_context+0xD58`, using an associated atomic counter at
`+0xD50`. Two static call sites are **not** proof of two executed
physics updates per present. Whether one or both are reached during
normal gameplay and what the accumulator represents remain unknown.
A plausible contributor to V9 acceleration is unexpected reconfiguration
of timing state or execution paths when `S8` becomes fractional,
but the cause of the V9 failure remains **unknown**.

See [FRAME_STEP_FOLLOWUP_ANALYSIS.md](FRAME_STEP_FOLLOWUP_ANALYSIS.md).
The next opt-in diagnostic is
[`guest_frame_step_cadence_probe.py`](guest_frame_step_cadence_probe.py),
with synthetic tests at
`tests/test_guest_frame_step_cadence_probe.py`. It resolves the
`X19` context, `X21` FPS state and `X20` timing configuration at
the original frame-step hook, verifies pointer relationships, removes
the temporary breakpoint, then takes sparse **numeric-only** snapshots
at multi-second intervals. Fields include `+0xD58` double accumulator,
`+0xD50` counter, `+0xD38` flags, `config+0x10/+0x14/+0x18/+0x1C`,
integer FPS at `X21+0x2C8`, and physical-counter timestamps. The
accumulator difference is NOT an independently established physics
call count. Tool has local synthetic tests, but live Eglantine behavior
is still **unverified**.

The user's confirmed baseline is that the unmodified game **runs in
slow motion below 60 actual FPS**; do not ask again. Failed V9
accelerated at ~30 FPS. No stable main/release is modified; do not
publish V10 or copyrighted game-code JSON. The second game build 33FA
still lacks this detailed E0F3-specific runtime mapping.


## 19. First sparse runtime simulation-accounting trace (~30 FPS, 2026-11-06)

The tester supplied the numeric-only `frame_step_cadence_30fps.json` from
**unpatched E0F3 gameplay around 30 displayed FPS**. The script took one
initial snapshot and five more after **requested 4-second free-running
intervals**. The frame-context integer counter `+0xD50` and
floating-point accumulator `+0xD58` were **equal in all 6 snapshots**:
**3297 → 3409 → 3531 → 3652 → 3772 → 3888** in both, with
increments **112, 122, 121, 120, 116**, total **+591**,
average **29.55 units per requested guest-running second**.

Every sample retained **integer FPS target 60**, timing config
**step 1.0, reciprocal 1.0, scaled value approximately 1/60,
nominal rate 60**. The original gameplay rate therefore does not
adapt its nominal config when actual rendering slows. The user has
already verified the unmodified game's slow motion below 60 FPS;
this counter evidence is consistent with that behavior. **Do not
re-ask the user about the baseline.**

Crucial caveat: the guest counter advanced **4.805–5.500 seconds**
between these snapshots, including *debugger pauses*. Dividing 591
by the whole **24.779 s** gives an artificial low ~23.9 units/s;
use the nominal four-second free-run windows for rough cadence, but
neither method is an independently verified per-present or physics
call count. The initially interrupted `+0x100` cache was
7,514,603 ticks (~240 ms) because of debugger interference; later
cached values were ~31–33.5 ms and align with prior steady 30 FPS
samples. Flags `+0xD38` alternated `0x2B` and `0x0B`
(bit 5), not yet mapped to a specific update path.

See [CADENCE_30FPS_FIRST_TRACE.md](CADENCE_30FPS_FIRST_TRACE.md).

**Next**: a short opt-in numeric-only GDB trace of the two *original*
E0F3 timing config call sites at **`main+0x006E6DD8`** and
**`main+0x006E70F8`**, both `BL main+0x03B4E300`.
[`guest_frame_step_path_trace.py`](guest_frame_step_path_trace.py)
checks original instructions before arming temporary breakpoints,
records which site was reached and live `S0/S8` values, then
single-steps original instructions and resumes the guest.
**It is not a FPS/cadence profiler:** debugger stops perturb timing.
At both call sites, `X21` has been repurposed since the original
`FDIV`; the helper deliberately reads the original FPS state via
`X19+0xA8 → manager+0x20` rather than trusting `X21`.
Synthetic tests are in `tests/test_guest_frame_step_path_trace.py`.
No new IPS is justified yet and no private code JSON belongs on GitHub.
