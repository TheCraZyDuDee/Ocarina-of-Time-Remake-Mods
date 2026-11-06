# First live gameplay frame-step trace — E0F3 (2026-11-06)

**Scope:** user-tested Eglantine/CachyOS, title `0400486024DEC000`,
updated `main` build `E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348`.
All FPS mods reported disabled, emulator target speed 100%, but hardware
could only deliver ~30 real FPS/~50% game speed without the mod.
The original, unmodified `fdiv s8,s1,s0` at `main+0x006E6CC4`
was independently verified by a separate GDB read-only preflight.
The `gameplay_timing_v2.json` file is a **private user-provided artifact**;
we only publish aggregated numbers and conclusions, never proprietary files.

## Major result: live frame-step operands identified

For **all 12 of 12** successive gameplay breakpoints immediately **before**
executing `fdiv s8,s1,s0`:

| Operand | Raw IEEE754 bits | Floating-point value |
| --- | --- | --- |
| `s0` (denominator) | `0x42700000` | 60.0 |
| `s1` (numerator) | `0x42700000` | 60.0 |
| `s8` (destination before division) | `0x00000000` | 0.0 |
| `s8` **after division** | **not sampled** | Mathematical result **1.0** |

Thus the **unmodified** frame-step division calculates `60 / 60 = 1.0`
when the actual emulator presents about 30 FPS and slows the game.
This original step does **not directly compensate** for the observed render
rate. *Conditional inference*: if this render-driven update executes once
per presented frame, 30 updates per second at one nominal simulation tick
per update yields half-speed movement. We still have **not instrumented the
number of calls per present**, nor verified how every downstream time
manager applies `s8`. Don't claim complete game-speed causality yet.

The actual vector registers were decoded from Eglantine's AArch64 GDB
`g` reply according to its own architectural register layout (33 u64
registers, CPSR u32, then 32 128-bit v registers). This supports a much
more reliable conclusion than guessing object fields.

## Timing candidate data (affected by breakpoints)

| Field sampled relative to x21 | Aggregated observation |
| --- | --- |
| `+0x100` (`u64`) | First `6,883,303`; other 11 `24,937,839–26,713,328`, median `26,499,606` |
| `+0x148` (`u64`) | Tracks `+0x100`; difference alternates between `256–395` and `468,389–714,140` |
| `+0x150` (`u64`) | Large unsigned representation of a negative signed quantity; decreases at each hook |
| `+0x2c8` (raw `u32`) | **60 = `0x0000003c`** at every hook. The old probe's interpretation of it as `float32` was incorrect. |

The decreases in `+0x150` correlate strongly (Pearson r ≈ **0.99995**)
with the **previous** `+0x100` sample, with residuals around `-77,562` for
the first transition, then alternating between about `-1,400` and
`-122,000` ticks. This supports a relation to frame accounting or elapsed
time. It does **not** establish the frequency/unit or exact write sites.

At a guest timer nominal frequency of 31,250,000 Hz, the ~25–27 million
values represent **0.80–0.85 seconds**, much longer than a normal frame.
**Debugger breakpoint, register-read, and single-step overhead dominates**;
this file cannot establish an unbiased per-frame duration or tell us whether
V9's clamp saturated during normal, uninstrumented gameplay.

## Correction to earlier hypothesis

The first menu trace found the raw bits at `x21+0x2c8` equal integer `60`,
not float 60. The new gameplay trace simultaneously reveals *the real
floating-point denominator `s0` is also 60.0*. These are distinct
observations; **do not infer they share a direct load/store provenance**.
The instruction originally disassembled as `ldr s0,[x21,#0x2c8]` can
have its result transformed/overwritten along the path to `fdiv`.
A local static dataflow trace of the complete region (with ZBIC-decoded
original NSOs) is required to determine the transition. It is unsafe
to patch `x21+0x2c8` as an assumed float field.

Also, a large `+0x100` sample under a paused GDB session **does not mean**
the field is necessarily an absolute monotonic timestamp. The previous
V9 saturation diagnosis is still a *hypothesis* for normal execution.

## Next high-value experiment: actual write-site provenance

The tester's Eglantine fork includes GDB remote **write watchpoints**
(`Z2`/`z2`), backed by `KProcess::InsertWatchpoint` and debug page marking.
An independently authored [local watchpoint helper](guest_timer_write_trace.py)
now uses the verified frame-step hook to discover the live `x21` object,
then watches **only the 8 bytes at x21+0x100** for a few writes, recording
the AArch64 writer PC as a `main+offset` location when possible.
This is more informative than further paused-frame duration sampling.

- Source includes no game executable code, copyrighted dumps or SDK code.
- Its synthetic protocol tests pass; **no live watchpoint trace yet**.
- The debugger may break **before or after** the store; recorded data does
  not assume either ordering.
- Watchpoints and breakpoints perturb performance; use only to locate writes,
  not to benchmark gameplay or estimate real frame rate.
- Original-opcode verification still fails closed; unknown other modules
  are reported as outside main rather than guessed.
- If a write never occurs or the fork rejects the watchpoint, stop this
  path; do **not** assume it validates V9.

Before V10, identify the precise write site, verify whether that field
tracks end-to-end *uninterrupted* frame duration rather than CPU-only or
partial update time, and map the downstream `s8` uses. Building another
IPS using only the trace would repeat V9's unsupported assumptions.

## Retrospective correction from later E0F3 code window

A later **verified private 1,024-byte static code excerpt** directly
resolves the above apparent contradiction: `main+0x006E6C98`
loads raw 32-bit integer FPS bits into `S0`, then
`main+0x006E6CA8` performs **`SCVTF S0,S0`**, numerically
converting integer 60 to float32 60.0. The earlier caution about
*unresolved* integer-to-float provenance at this site is thus
superseded **for E0F3**. This does not establish downstream frame
frequency or validate any patch. See
[FRAME_STEP_CONSUMERS_FIRST_TRACE.md](FRAME_STEP_CONSUMERS_FIRST_TRACE.md).
