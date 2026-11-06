# Developer / AI handoff — Ocarina of Time true dynamic FPS

> **Read this first if continuing the project in a new chat, with another AI,
> or with a different developer.** This file is intended to stand alone.
> Status: **NOT SOLVED**; last playable experiment **V9 FAILED**.
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
- `s0 = *(float *)(x21 + 0x2C8)` (current FPS target).
- `s1` is selected as **60.0 or 30.0**, based on a state flag.
- `fdiv s8,s1,s0`: **simulation step = base_rate / target_fps**.
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

## 6. Remaining technical blocker and recommended next method

**Find a real, monotonic elapsed-frame-time source with validated
provenance.** No such in-game field is confirmed today.

A successor should:

1. Identify where the FPS state `+0x100` field is written and its units.
   Do not guess from nearby offsets, names, or compiler layout.
2. Use **non-invasive guest debugging or an emulator-side trace** at
   `main+0x006E6CC4` (E0F3) / `main+0x006B5A08` (33FA)
   to record `target_fps`, `s8`, the supposed time sample,
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
