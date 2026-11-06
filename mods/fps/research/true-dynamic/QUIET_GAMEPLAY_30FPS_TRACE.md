# Second sparse gameplay timer trace: ~30 FPS on E0F3 (2026-11-06)

**Status: successful two-condition timing correlation; not a complete dynamic FPS mod.**

The tester supplied the private numeric-only `quiet_timer_snapshots_30fps.json`
captured during E0F3 gameplay, reporting about 30 FPS and five snapshots
after approximately four seconds of free-running guest execution each.
The previously documented 50 FPS test used the same script and five samples.

| Measure | Prior ~50 FPS | New ~30 FPS |
| --- | ---: | ---: |
| `X21+0x100` mean duration | 22.106 ms | **33.450 ms** |
| `+0x100` range | 20.002–23.043 ms | **31.469–35.233 ms** |
| `+0x100` implied instantaneous FPS | 43.4–50.0 | **28.38–31.78** |
| `+0x148` mean duration | 18.699 ms | **19.791 ms** |
| `+0x148` range | 17.342–20.713 ms | **19.275–20.498 ms** |
| Number reaching V9 4-tick cap | 0/5 | **0/5** |

The new `+0x100` tick counts range **983,403–1,101,034**, mean
**1,045,311.2 ticks** at 31.25 MHz. The theoretical 30 FPS delta is
**1,041,666.7 ticks = 33.333 ms**. The new mean is 33.450 ms, only
~0.117 ms above that nominal frame duration. Over the two workloads,
the mean cached duration rose by **51.3%**. Earlier ~50 FPS was an
approximate overlay label, not an exact continuous measurement, so the
expected ratio must not be overinterpreted.

The `+0x148` value stayed near 20 ms as the FPS dropped, supporting
the earlier hypothesis that it measures a shorter stage or partial
time interval, not the entire frame. The measurements do **not identify
which subsystems or GPU/present wait phases are included**.
`+0x108` advanced ~4.145–4.175 seconds between samples, compatible
with the four-second free-running windows plus debugger overhead.

## Implication for failed V9

At nominal 60 Hz, V9 computes
`clamp(60 * time_ticks / 31_250_000, 0.5, 4.0)` using `+0x100`.
The new **unpatched-game** values would produce **1.888–2.114 ticks**
if the helper read them fresh and ran as intended. All samples
remain well below the saturation threshold **2,083,333 ticks**.

The 50 FPS and 30 FPS captures strongly contradict a blanket theory
that `+0x100` always contains an absolute cumulative counter or that
V9 would *necessarily* hit its maximum in ordinary unmodified gameplay.
They do **not** directly measure V9's state under patching. V9's
observed speed-up near 30 FPS is still real; possible causes include
timer update/use order, differing patch behavior, duplicated or
partially independent update loops, incorrect frame-step consumers,
and other unvalidated effects. None is proven by these captures.

## Next: stop collecting the same timer values and inspect the update path

The timer's origin (`CNTPCT_EL0`), frequency (31.25 MHz) and
FPS-dependent cached delta are now supported by independent static
and runtime evidence. The high-value remaining questions are:

1. Which computations consume the result of the original
   `fdiv s8,s1,s0` at E0F3 `main+0x006E6CC4`?
2. Is `+0x100` refreshed before or after each simulation update?
3. How many times does the simulation update execute per displayed
   frame, and what is the interaction with menus/physics?
4. Why did V9 accelerate despite access to a plausible timer source?

A new **read-only** `guest_frame_step_static_window.py` tool will
capture a bounded original-code window from the private guest at the
verified E0F3 frame-step function. This is useful for initial static
downstream dataflow and call-target analysis, but **cannot by itself
prove runtime call counts**. The JSON contains copyrighted original
instruction words and must remain private. No new IPS / V10 yet.

Full 33FA static mapping and runtime verification are still needed.
