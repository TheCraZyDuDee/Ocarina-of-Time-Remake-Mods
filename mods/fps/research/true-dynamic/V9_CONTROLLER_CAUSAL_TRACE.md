# E0F3 V9 controller: verified rate/presentation inconsistency (2026-11-06)

**Result: an independently verified structural inconsistency in the archived V9 patch. NOT a verified causal diagnosis of its gameplay speed, and not a working mod.**

The user supplied the private original E0F3 guest-code capture `v9_controller_original.json` from `guest_v9_controller_window.py`. Its **2,048 bytes / 512 original AArch64 words** are SHA-256 verified against the supplied `3a17158490bb88a05d3a3afcff0ec6141f9154ee5d9848feb4363a9996154728`. Both source fingerprints match the archive's V9 original-code expectations: conditional guard at `main+0x03B4EF90` and presentation argument load at `main+0x03B4F080`. **No original code bytes, private dumps or large proprietary instruction sequences are committed.**

## Controller entry, guards, and rate selection

The controller's captured function starts at **`main+0x03B4EF60`**. Its `X0` is a controller object (preserved in `X20`); its `X1` is a timing object (preserved in `X19`).

- **`main+0x03B4EF84`** reads a byte from `controller+0x60`.
- **`main+0x03B4EF90`** performs `TBNZ W8,#0,main+0x03B4F074`, skipping the *adaptive recalculation* when controller flag bit 0 is set.
- On the normal fallthrough, the routine next checks that `timing+0x140 >= 1`; otherwise it also skips recalculation to `main+0x03B4F074`. **Therefore V9's guard NOP only removes the flag check, not this separate sample-count guard.**
- With sufficient timing observations, it reads 64-bit elapsed measurements at **`timing+0x148` and `timing+0x150`**, converts them against the same shared tick-conversion routine at `main+0x00E3A5C0`, scales with **60.0f**, adds per-controller adjustments `+0x08/+0x0C`, chooses a dominant estimate, and converts the resulting candidate to an integer interval.
- Several lower/upper limits, counters and change-acceptance conditions update **`controller+0x48`**, the persistent presentation interval; e.g. the normal path writes `W21` to `+0x48` near `main+0x03B4F058`. The branch body also modifies `+0x4C/+0x50/+0x54` and other derived timing fields.

The captured routine does not show any need to identify `controller+0x60` by a guessed high-level name: the proven fact is that **bit 0 gates recalculation**, not the two common apply calls that follow.

## Exact shared rate and present calls

Both guard paths rejoin at **`main+0x03B4F074`**:

1. The controller calls an internal helper at **`main+0x03B4F160`** via `BL` at **`main+0x03B4F07C`**. The helper reads the stored **`controller+0x58`** integer. Its value was derived as **`60 / interval`** by `SDIV` in the controller at `main+0x03B4F05C` (rounded via integer truncation). The helper passes this integer FPS rate to the previously verified shared setter at **`main+0x004DC0F0`**, called at **`main+0x03B4F190`**. The helper handles the native setter's success or suggested fallback independently.
2. Immediately afterward, the controller loads **`W1=[controller+0x48]`** at **`main+0x03B4F080`**, sets `X0=timing object`, and calls the verified **presentation/swap setter at `main+0x0346C5C0`** from **`main+0x03B4F088`**.

**Original coordinated behavior:** rate setter and presentation setter normally receive values derived from the **same persistent interval** (`rate≈60/interval` versus `interval`), subject to native validation, fallback and other guard state.

**What failed V9 changes:**

| E0F3 edit | Original behavior | V9 behavior |
| --- | --- | --- |
| `main+0x03B4EF90` | Conditionally skip adaptive candidate recalc if `controller+0x60 & 1` | NOP: force evaluation of subsequent sample-count guard and possibly recalc |
| `main+0x03B4F080` | Load presentation argument from current `controller+0x48` | Force `W1=1` **regardless** of calculated/accepted interval |
| `main+0x006E6CC4` | Native `S8 = S1/S0` | V9 physical-counter elapsed-step helper and clamp |

Hence **if** the controller has selected a persistent interval different from 1 (e.g. 2 for nominal 30 FPS, 3 for nominal 20 FPS), V9's shared FPS setter still receives a rate based on the stored interval (e.g. 30 or 20 FPS), but the presentation setter always receives 1. **This is a proven structural mismatch in V9's patched source**, conditional on the runtime interval not being 1. It is a compelling testable contributor to contradictory pacing and simulation acceleration. It is **not proof** that interval !=1 in V9's failed ~30 FPS gameplay, or that this mismatch is the sole source of excessive gameplay speed. The other V9 hook, feedback/selector state and timing callback still matter.

## Why previously observed unpatched data matters

- The user's unpatched game runs in slow motion when physical rendering drops below 60 FPS.
- Independent quiet original-gameplay samples show `X21+0x100` timing deltas near ~22.1 ms at ~50 FPS and ~33.45 ms at ~30 FPS.
- The unpatched `S8=1` and `config nominal=60` path is active at ~30 FPS, confirmed by numeric accumulator/callsite traces.
- V9 combined this physical elapsed-time scaling with **a forced one-interval presentation and a guard bypass**. None of those original-game captures prove the *patched-game* controller's selected interval or actual application order.

## Prioritized next work

We have enough original E0F3 code to statically isolate the *causal knobs*: a skipped interval-recalculation block, a rate setter taking `60/interval`, a present setter taking `interval`, and a separate simulation step.

**Do not make another combined V10 attempt.** The next authorized research stage should be one-change-at-a-time experiments with original source-byte guards and obvious rollback paths, or a short numeric-only patched-game telemetry capture if users accept a known-failed research patch. However, replaying V9 is not necessary merely to explain its static inconsistency. We should determine native allowed presentation intervals, whether a rate config callback writes that interval behind the controller, and how to keep simulation time independent of presentation pacing.

The uploaded raw JSON and any generated disassembly remain private, the GitHub branch remains `research/true-dynamic-fps` only, and no release ZIP/IPS is published. Detailed 33FA equivalence is NOT established from this E0F3 capture.


## Correction after full FPS/presentation source batch (2026-11-06)

The native presentation setter at `main+0x0346C5C0` does more than
forward the controller interval. It writes **`timing+0xFC =
60/interval`** (or 60 if interval zero), so V9's forced `W1=1`
also forces that rate field to 60. The original cached elapsed counter
is `timing+0x100`, **not the same field**. Native shared FPS setter
at `main+0x004DC0F0` has a state-gated special path for
requests >=40 that can bypass the normal divisor-of-60 requirement.
The callback at `main+0x02F52DF0` is independently confirmed to
consume `config+0x10` variable step for per-object countdowns and
interpolation; it has no direct BL call to these two FPS/present
setters in the verified 4 KB window. None of this proves that
V9's actual stored interval differed from 1 or exactly why it ran
fast. See [TIMING_BATCH_2026_11_06.md](TIMING_BATCH_2026_11_06.md).
