# V9 failure: unresolved interaction of presentation, guard and step

**Status: V9 failed gameplay testing. Do not use it for normal play.**
**Current strongest verified source finding:** Original E0F3 presentation
setter stores `timing+0xFC=60/interval`; V9 forced interval 1, while its
rate controller still derives 60/stored interval and V9 separately
modifies the simulation step. A 9,216-byte private source batch also
confirmed that the optional config callback genuinely uses variable
step for per-object countdowns and interpolation. **The runtime V9
root cause is still unknown.** Earlier four-tick saturation was a
historical hypothesis weakened by unpatched 30/50 FPS timer captures;
do not present it as the leading proven cause. See
[TIMING_BATCH_2026_11_06.md](TIMING_BATCH_2026_11_06.md).

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


## Original-game frame-step accumulator trace (~30 FPS, 2026-11-06)

Live sparse numeric snapshots during unpatched E0F3 gameplay around 30
FPS show `frame_context+0xD50` and `+0xD58` increased together by
**591** units over five requested four-second free-running intervals
(~29.55 units per nominal running second), with exact equality in all
six snapshots. The derived rate configuration remained **step 1.0,
reciprocal 1.0, and nominal 60**. This supports the unpatched
slow-motion baseline, not the cause of V9's opposite acceleration.
The guest-counter elapsed intervals also included debugger stop time,
so the result is a coarse state progression observation, not a precise
runtime physics call count. The next step is determining which of the
two verified timing configuration call sites actually runs in gameplay
and whether `S8` reaches it on both paths. See
[CADENCE_30FPS_FIRST_TRACE.md](CADENCE_30FPS_FIRST_TRACE.md).


## Active gameplay callsite and fractional rate risk (2026-11-06)

A short numeric-only E0F3 original-game trace captured eight calls at
`main+0x006E70F8` into timing-config converter
`main+0x03B4E300`. Each received `S0=S8=1.0`, with frame flags
`0x0B`, target 60 and `+0xD50` integer counter increasing by
one each hit. The alternate `main+0x006E6DD8` call did not fire
during this brief sample. Timing is perturbed by debugger stops.

The converter produces **rounded nominal rate `60/step`**. Applying
the *source formula* to previously recorded **unpatched** gameplay
counter values yields hypothetical 50 FPS-scene rates
**50,44,46,43,44**, and 30 FPS-scene rates **32,31,29,30,28**.
Only one out of ten is an exact integer divisor of 60; a separately
verified general FPS setter rejects non-divisor rates. **It has not
been established that the converter passes its rate into that setter
in normal or V9 execution**, so this is a precise compatibility
hypothesis, not an explanation proven to cause V9's acceleration.

V9 additionally modifies a guard at `main+0x03B4EF90` and a
presentation argument at `main+0x03B4F080`, in addition to the
frame-step hook at `main+0x006E6CC4`. These three changes are
not causally isolated in user gameplay reports. Future source-only
analysis should map whether their interactions force reconfiguration
or duplicate simulation. Do not use known-failed V9 for normal play.
See [FRAME_STEP_PATH_30FPS_FIRST_TRACE.md](FRAME_STEP_PATH_30FPS_FIRST_TRACE.md).


## Correction: E0F3 flag bit 1 selects distinct config-call paths

A later **verified source-level control-flow graph** of the contiguous
2816-byte E0F3 frame-step excerpt resolves a potentially misleading
interpretation of the two callsites. A `TBNZ` on `W9` bit 1
(`frame_context+0xD38`) at `main+0x006E6CC8` selects between a
first `+1/+S8` accounting path (callsite
`main+0x006E6DD8`) and a second accounting path (callsite
`main+0x006E70F8`). **There is no in-window direct-branch path
from the first call's continuation to the second call**, or vice versa.
Two static callsites alone therefore do **not** establish duplicated
simulation steps per invocation. The original eight-hit gameplay
trace had flags `0x0B` (bit 1 set) and took the second path,
consistent with this control flow.

Flags `0x2B` found earlier also have bit 1 set. The extra bit 5
is explicitly `LDSET` and `LDCLR` around a callback region,
consistent with an in-progress flag, not necessarily a distinct
simulation/update mode. Bit 5's complete lifecycle is not proven.

See [E0F3_FRAME_STEP_BRANCH_GRAPH.md](E0F3_FRAME_STEP_BRANCH_GRAPH.md).
Do not attribute failed V9's excessive speed to two calls per frame
without a measured, **patched-game** call trace or other independent
evidence. The native timing callback and V9's three-way changes
remain higher-priority unresolved causes.


## Verified source mismatch: V9 rate vs presentation (2026-11-06)

The tester's checksum-verified private **original E0F3 controller**
window gives the missing control flow. The interval controller at
`main+0x03B4EF60` skips adaptive recalculation when its
`controller+0x60` flag bit 0 is set, but still calls both native
FPS and presentation setters. Its normal FPS setter reads a
`60 / interval` rate derived from `controller+0x48`, while its
presentation setter receives that stored interval directly.
V9 replaces the first guard with `NOP` and the presentation load
with `MOV W1,#1`, while separately changing `S8`.
**If the stored interval is 2 or 3**, for example, the native FPS
setter may request approximately 30 or 20 FPS (subject to
acceptance/fallback) while presentation is forced to interval 1.
This conditional structural inconsistency is independently proven
in patch source and original controller code. Its real effects,
V9's stored interval and the observed overspeed cause remain unknown.
See [V9_CONTROLLER_CAUSAL_TRACE.md](V9_CONTROLLER_CAUSAL_TRACE.md).


## Callback presence established, role still unverified (2026-11-06)

The tester's original-game E0F3 callback resolver found that
`config+0x1C8` **is non-null in gameplay**, and the virtual
callback method is **`main+0x02F52DF0`**. A SHA-256-verified
128-byte source excerpt begins the callback function, but branches
extend beyond the captured bytes. **The destination's behavior is
unproven**: presence alone does not establish a feedback loop into
either native FPS or the presentation setter. Do not label that as a
confirmed V9 failure cause.

To minimize repeated emulator launches, the guarded research tool
[`guest_timing_batch_capture.py`](guest_timing_batch_capture.py)
collects extended callback, native FPS setter, and presentation setter
code in one private, original-game read-only snapshot. See
[ONE_SHOT_TIMING_BATCH_GUIDE.md](ONE_SHOT_TIMING_BATCH_GUIDE.md).
The existing V9 source mismatch remains verified conditional on the
controller's stored interval differing from 1. No new IPS was made.
