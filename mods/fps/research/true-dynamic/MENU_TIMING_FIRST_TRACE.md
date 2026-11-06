# First live menu timing trace (E0F3, 2026-11-06)

**Status:** 12 samples received from the user, original hook verified at
`main+0x006E6CC4`. **Do not publish the private JSON, raw log, dumps,
addresses or private saves**. This document contains numerical aggregate
observations only and is suitable for the research branch.

## Experimental conditions and limits

The user ran Eglantine with its GDB stub on port 6543 under Linux, no
intentional FPS mod enabled. The current game was updated build E0F3.
The debugger verified `fdiv s8,s1,s0` had the expected original opcode.
The script sampled 12 consecutive breakpoints **at the exact division**,
resuming with a single-step and rearming the trap between observations.

**Critical measurement limitation:** each debugger stop and step perturbs
the guest clock. These samples are *not real uninstrumented frame durations*.
Do not extrapolate values to normal play. The first sample had a different
delay from subsequent samples, consistent with entry/interrupt overhead.

## Measured values and relationships

| x21 field | Captured data | Interpretation |
| --- | --- | --- |
| `+0x100`, u64 | First 7,304,669; remaining 25,619,571–26,033,917; median of remaining samples ≈25.84 million | V9's presumed frame-duration input. Affected heavily by debugger pauses. |
| `+0x148`, u64 | Tracks `+0x100` within **209–384** integer ticks | Strong evidence the two fields are related but not proof of semantics or units. |
| `+0x150`, u64 | Huge unsigned value, decreasing on every sample | May be a signed/negative accumulator or offset; **not an ordinary small positive frame duration**. |
| `+0x2c8`, four bytes | Bit pattern `0x0000003c`, constant across all samples | As uint32 this is 60. Interpreted as float32 it is `8.407790785948902e-44`, **NOT** 60.0f. The old probe's `target_fps` label was invalid. |

One noteworthy relationship: after each sample, the **decrease**
in the `+0x150` field is within approximately 0–124,004 ticks of the
*preceding sample's* `+0x100` value, and the correlation over the
11 observed transitions is about **0.99996**. This is consistent with
frame-based accounting and undermines the premature statement that
`+0x100` must be an unrelated absolute counter. Correlation alone
does **not** prove the variables' origin or tick units.

At 31.25 MHz, the observed `+0x100` samples correspond to ~0.23 s
for the first and ~0.82–0.83 s for most subsequent samples. A normal
60 FPS frame would be ~0.0167 s, so breakpoint overhead dominates.
Every sample exceeds the V9 upper clamp threshold (~2,083,333 ticks at
nominal 60 Hz), **but this does not prove saturation occurs when the
game runs without debugger interruptions.**

## Immediate correction to our previous research

**Previous theory (too strong):** V9's `+0x100` field must be a
cumulative or unrelated counter because it saturates the maximum step.

**Current conclusion:** The field is correlated with another nearby
field and with an apparently accumulating negative value. It *could*
be a duration whose sample is massively inflated by GDB pauses.
We **still do not know what it contains in uninterrupted gameplay**.
V9's failed over-speed test remains genuine, but this trace alone
does not explain its precise mechanism.

The probe also incorrectly called `x21+0x2c8` a float target FPS
when the underlying bits are `0x0000003c`. This is a typing/pointer
or call-path interpretation error in the probe or our static map.
**Do not claim `s0` at the original division was measured here.**
The trace did **not** capture actual FP register operands.

## Next experiment

The independently written GDB diagnostic now reads Eglantine's actual
AArch64 `v0`, `v1` and `v8` register contents from the `g` packet,
as their low-32-bit `s0`, `s1`, `s8` representations. The
GDB architecture layout is publicly documented by the emulator code:
33 64-bit GPRs, CPSR u32, then 32 128-bit vector registers.
This captures the actual denominator and numerator **right before**
`fdiv s8,s1,s0` without guessing an object's field type.

Obtain one **gameplay** trace with the corrected script using the current
session's `eden_log.txt`, **all FPS mods disabled** and original
hook verified. It can distinguish whether this division's live
inputs reflect 60, 30, or another value, and whether `+0x2c8`
belongs to the relevant object's FPS setting. The breakpoint-induced
timer inflation remains; do not use this trace as a performance test.

Do not generate V10 merely from these samples. A safe timer source
still needs writer-site analysis, lifecycle handling and an
uninterrupted runtime measurement.
