# V9 failure: suspected four-tick saturation

**Status: V9 failed gameplay testing. Do not use it for normal play.**

## User-reported results

- Around **15 FPS**, gameplay feels close to normal speed.
- Around **30 FPS**, movement, physics and animations become much too fast.
- Below **15 FPS**, gameplay still slows down.
- The problem closely resembles V8A despite V9's extra timer-reading code.

These are qualitative gameplay observations, not instrumented speed or timer measurements.

## Verified V9 patch mechanics

Reading the actual V9 IPS32 packages confirms that **both build variants**
install the same calculation:

1. Load a 64-bit integer from a field at `controller + 0x100`.
2. Convert it to single-precision float.
3. Multiply by a nominal 60 or 30 Hz value and divide by guest timer
   frequency (`CNTFRQ_EL0`).
4. Clamp the result to **0.5–4.0** simulation ticks per rendered frame.
5. Feed it to the game's existing floating-point simulation multiplier.

The ARM64 instruction sequence and associated hook placement were statically
checked, but **the field at +0x100 was never proven to contain a per-frame
time delta**. V9's prior documentation overclaimed this. It might be a
cumulative time counter, a differently scaled value or an unrelated field.
This statement reflected the original V9 analysis. Subsequent live debugger
samples and write-watchpoints have captured candidate field values and one
consistent E0F3 writer PC. See TIMER_WRITER_FIRST_TRACE.md for details.
Those paused-debugger values do **not** establish that V9 saturated during
uninterrupted gameplay.

## Why the four-tick clamp matters

At a nominal 60 simulation updates per real second, if the value fed into
the game stays at `4.0`, expected speed depends directly on rendered FPS:

| Rendered FPS | Simulation ticks per second | Implied speed |
| --- | --- | --- |
| 5 | 20 | 33% |
| 10 | 40 | 67% |
| 15 | 60 | 100% |
| 20 | 80 | 133% |
| 30 | 120 | 200% |
| 45 | 180 | 300% |
| 60 | 240 | 400% |

This pattern closely matches the tester's report. **It suggests saturation,
but does not prove that saturation actually occurred.**

The upper clamp is reached whenever the input is large enough:
`input_ticks >= 4 * CNTFRQ_EL0 / nominal_hz`. At 31.25 MHz and
nominal 60 Hz, that is about **2,083,333 ticks** (66.7 ms). If the value
is an *absolute* timer, it would quickly pass the threshold and remain
clamped on every frame, regardless of actual FPS.

## What we must establish before V10

- Identify where any proposed timing field is written and whether it changes
  **once per completed presentation**, not just per simulation tick.
- Confirm the units (ticks vs ns vs microseconds vs CPU/GPU completion cycles).
- Confirm that samples include CPU stalls, GPU fences, rendering, vsync and
  guest timing as required, rather than measuring only part of a frame.
- Observe the field at 15/30/60 FPS including menus and after loading saves.
  For a true delta at 31.25 MHz, one would expect roughly
  2.08m / 1.04m / 0.52m ticks respectively.
- Alternatively, use a *known monotonic* guest counter
  (`CNTPCT_EL0`), but this requires separately validated, persistent,
  writable storage of the previous sample, lifecycle initialization and
  correct guest register preservation. Arbitrary text padding or
  unverified struct offsets are not safe substitutes.
- Only construct a new IPS when all these conditions are met.

A render-driven game cannot maintain updates at literally 0 rendered FPS
without an independent simulation worker. Extremely low performance may
also prevent real-time fixed-step catch-up despite correct code.

## Actions

V9 is now marked **failed / not for use** and its source builder is
disabled by default; it can be rebuilt only through a deliberately
named research-reproduction override. No broken IPS ZIP is committed to GitHub.

Previous fixed 30 FPS and discrete native adaptive mods on `main`
are unchanged.

See [the offline failure model](v9_failure_model.py) and
[its regression tests](../../../../tests/test_v9_failure.py).


## Update: real physical-counter duration observed around 50 FPS (2026-11-06)

Subsequent E0F3 source tracing established that the `+0x100` producer
subtracts two `CNTPCT_EL0` readings. The first sparse, comparatively
non-invasive unmodified-gameplay run recorded five cached `+0x100`
values equivalent to **20.0–23.0 ms**, matching the tester's approximate
**50 FPS** overlay. All five were below the 4.0-tick saturation
threshold of 66.7 ms at nominal 60 Hz. The observed source is **not a
simple cumulative absolute timestamp** under these conditions.

The four-tick saturation explanation remains a **hypothesis for failed
V9 gameplay**, not a verified diagnosis. Unmodified 50 FPS samples
cannot tell us what values V9 received at ~30 FPS, whether the field
was updated at the right time, or whether its replacement simulation
multiplier affected subsystems differently. Focus on timing order,
actual render/update cadence and downstream consumers before another IPS.
See [QUIET_GAMEPLAY_FIRST_TRACE.md](QUIET_GAMEPLAY_FIRST_TRACE.md).


## Second timing condition around 30 FPS (2026-11-06)

A second **unpatched E0F3** sparse gameplay trace at approximately 30
FPS recorded `X21+0x100` duration values of **31.469–35.233 ms**
(mean **33.450 ms**), consistent with the expected 33.333 ms period.
These would yield **1.888–2.114 V9 steps** at nominal 60 Hz if
sampled fresh by the V9 helper. None reached the 4-tick cap threshold.
The separate `+0x148` field remained near **20 ms**. Taken with the
prior ~50 FPS data (22.106 ms mean `+0x100`), this supports a useful
FPS-sensitive timer but **does not demonstrate V9's live inputs or
correctness**. The speed-up could still arise from stale inputs in the
patched mode, update order, duplicated updates or other issues.
Further timer snapshots are lower priority than static and runtime
analysis of `s8` consumers. See
[QUIET_GAMEPLAY_30FPS_TRACE.md](QUIET_GAMEPLAY_30FPS_TRACE.md).
