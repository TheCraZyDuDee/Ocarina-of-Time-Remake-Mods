# First sparse gameplay timer trace at approximately 50 FPS (E0F3, 2026-11-06)

**Evidence: private numeric-only debugger snapshots. Not a working FPS mod.**

The tester supplied `quiet_timer_snapshots.json` from Eglantine during gameplay on
E0F3 (`E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348`) with FPS
patches disabled. The overlay showed **about 50 FPS**; the script let
the game run approximately four seconds between five brief debugger
interruptions. This is a sparse sample of **cached** game timing fields,
not a true frame-time distribution or benchmark.

## Quantitative result (aggregated; raw private JSON remains uncommitted)

| Measurement | Result |
| --- | --- |
| E0F3 `x21+0x100` unsigned guest ticks | 625,074–720,094 (5 samples) |
| Same at 31,250,000 Hz | **20.002–23.043 ms** |
| Mean and median cached duration | **22.106 ms** and **22.628 ms** |
| Equivalent single-frame rate if complete duration | **43.4–50.0 FPS** |
| `x21+0x148` | **17.342–20.713 ms** |
| `+0x100 - +0x148` | **2.213–4.638 ms** |
| `x21+0x108` advancement between snapshots | **4.158–4.171 seconds** |
| V9 upper four-tick clamp threshold at 60 Hz | **2,083,333 ticks = 66.667 ms** |
| Samples at or above that threshold | **0/5** |

The observed `+0x100` magnitude is consistent with elapsed **frame-like**
time at the user's approximately 50 FPS display. The timer is already
known to originate from `CNTPCT_EL0`, and `+0x108` advances at roughly
the expected rate while the game runs, with extra debugger overhead.
This is substantially stronger support for useful timer provenance than
the earlier ~0.8 s pause-contaminated per-frame breakpoint traces.

In the static writer, the **`+0x148` sample is computed before a
virtual callback**, and the `+0x100` sample is computed later.
The persistent ordering `+0x148 < +0x100` is compatible with distinct
partial and longer measurement windows; it does **not prove**
`+0x100` includes the whole presentation/vblank interval.

## Updated reading of V9's failure

The earlier handoff proposed that V9 might have stayed saturated at four
ticks per frame. These **unmodified-game** samples do **not** support
*permanent* saturation around 50 FPS: if V9 read these exact samples at
the intended time and its helper operated as designed, its computed
uncapped step would be approximately **1.20–1.38 60-Hz ticks**.
No sampled value reaches the four-tick cap.

**This does not rule out V9 saturation** during 15–30 FPS gameplay,
emulator stalls, loading, altered scheduling caused by V9 itself, or
different states. It is also not evidence that V9 executed its helper
correctly, that the game used the value once per presented frame, or
that scaling `s8` drives all physics. The V9 user-observed fast
gameplay near 30 FPS remains a failure.

This means the next investigation should prioritize **measurement
lifecycle and use**, not simply replacing the counter source. The
simplistic unconditional 'V9 input is an absolute timestamp, so
it always maxes at four ticks' explanation is now contradicted by
the statically verified delta writer and this first ordinary-play
sampling window.

## Next defensible test

**Reuse** `guest_timer_quiet_snapshot.py` (no new IPS) in a different
stable gameplay workload that naturally produces around 30 FPS,
with Eglantine at 100% speed, all FPS mods disabled, and no frame
generation. Adjust only the user-observed `--fps-label`.
Do not use emulator-speed throttling to manufacture 30 FPS: it may
alter the relationship between guest counter progression and
wall-clock time. If no natural lower-FPS scene is available, do not
force one.

A genuine complete-frame 30 FPS delta at 31.25 MHz is approximately
**1,041,667 ticks / 33.333 ms**. We want to see if `+0x100` follows
that change while `+0x148` stays shorter. Report the actual overlay
reading and whether the game itself runs at normal, slow or fast
speed. The capture should remain private; commit only aggregated
conclusions and source-only diagnostics.

**Before V10:** verify whether `+0x100` is refreshed before each
`fdiv s8,s1,s0` simulation step, how often that division executes
per present, and how downstream physics loops consume `s8`.
Keep both supported builds in scope; current live evidence is E0F3 only.
