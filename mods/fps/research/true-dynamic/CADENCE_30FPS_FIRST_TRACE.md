# First live sparse frame-step accumulator / cadence trace (~30 FPS, E0F3; 2026-11-06)

**Status: original-game simulation accounting now linked to ~30 FPS slowdown. Not a verified physics function call count and not a fix for V9.**

The tester privately supplied `frame_step_cadence_30fps.json`, produced by `guest_frame_step_cadence_probe.py` in a steady gameplay scene with the emulator overlay around 30 FPS, all FPS IPS patches disabled, emulator speed 100%, and five requested 4-second free-running gaps. The report is numeric telemetry; do not commit the raw JSON.

## Key results

| Property | Observed |
| --- | --- |
| Build | E0F3 |
| Cached FPS target `X21+0x2C8` | **Integer 60** in all six snapshots |
| Rate config `+0x10` / `+0x14` | **step 1.0 / reciprocal 1.0** in all six |
| Rate config `+0x18` | **~0.0166666675**, effectively 1/60, in all six |
| Rate config `+0x1C` | **Nominal rate 60** in all six |
| Frame context `+0xD50` integer counter | **3297 → 3888** (total +591) |
| Frame context `+0xD58` double counter | **3297.0 → 3888.0** (total +591.0) |
| Equality of `+0xD50` and `+0xD58` | **6/6 snapshots** |
| Changes over 5 requested 4-second runs | **+112, +122, +121, +120, +116** |
| Mean change per requested 4 seconds | **118.2** |
| Equivalent change per nominal free-running second | **29.55 units/s** |
| `+0xD38` flags | **0x2B or 0x0B** (differ by bit 5) |
| Guest counter time between snapshots | **4.805–5.500 seconds**, including debugger overhead |

The first sample's cached `+0x100` delta is **7,514,603 ticks (~240.5 ms)**, clearly affected by the debugger attach/pause. Later cached deltas are **969,681–1,045,839 ticks (~31.0–33.5 ms)**, compatible with the previous original-game 30 FPS trace. **Do not use the initial 240 ms value as a natural frame duration.**

Each observed increase in the double accumulator matches the integer counter increase exactly. This is consistent with the original `S8=1.0` frame-step machinery incrementing the accumulator and associated integer state in lockstep, approximately 30 times per 4-second game-running interval. However, **the two counters could be connected by additional code and are not themselves independently verified game physics call counts or presents**.

**Important measurement caveat:** The script's `time.sleep(4)` lets the guest run about 4 seconds between interrupts. The `previous_counter_108` differences include time spent paused for debugger communication and are 4.8–5.5 seconds. Dividing the integer counter increments by *those entire differences* yields ~20–25 units/s, but that underestimates free-running cadence because the guest was stopped for part of the elapsed time. The 29.55 units/s figure is approximate and contingent on the requested sleep windows, not a high-precision performance measurement.

The user has already confirmed: **the unmodified game runs in slow motion below 60 actual rendered FPS**, the motivation for this project. Do not ask them again to verify this baseline.

## Implication for V9 and next experiment

The original game's nominal 60-step configuration stays at 60 while the accumulator advances at about 30 units per running second. A naively corrected step of ~2.0 at ~30 FPS would *arithmetically* deliver ~60 accumulator units/s, but the code also passes the step to `main+0x03B4E300`, recalculating `config+0x10`, reciprocal `+0x14`, derived nominal rate `+0x1C` and related fields. **This is not proof that simply doubling S8 would fix gameplay**, because presentation pacing, config callbacks, branch selection, and different physics substeps may respond differently.

V9's real gameplay failure is still unexplained. We know the original clock `X21+0x100` measures a plausible physical-counter duration near 30 FPS and does not normally hit the 4-tick clamp during uninterrupted unmodified gameplay. We do **not** know what happened to V9's cached values and configuration after its own presentation/guard patches were applied.

The next high-value provenance test is a **short breakpoint path trace at both original E0F3 call sites** leading to `main+0x03B4E300`: `main+0x006E6DD8` and `main+0x006E70F8`. Record which sites actually run in gameplay, sample the incoming floating-point step (`S0`/`S8`), and relate active path to flag bits. This will perturb timing and therefore is **not an FPS/clock benchmark**. The output should contain only numeric values and code offsets, not original game bytes.

Alternatively, a true emulator-side **non-pausing** trace would be needed to establish the exact number of calls per presented frame. Do not build/publish V10 until the live path and update semantics are better characterized.

All changes remain on research branch. Stable main/releases unchanged. Base 33FA still needs independent mapping.
