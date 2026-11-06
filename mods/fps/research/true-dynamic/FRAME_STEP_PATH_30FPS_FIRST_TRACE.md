# Normal-gameplay timing-config path confirmed (E0F3, 2026-11-06)

**Research only. The original game slows below 60 actual FPS, and V9 is still a known failed patch.**

The tester supplied a private numeric-only `frame_step_paths_30fps.json`
from a gameplay scene at approximately 30 FPS, after running the opt-in
`guest_frame_step_path_trace.py` GDB probe with all FPS patches disabled.
The report contains eight short software-breakpoint hits. No original game
instructions, private raw instruction windows, guest addresses or keys are
published here.

## Observations (eight sequential hits)

| Checked state | Result |
| --- | --- |
| Verified E0F3 timing-config callee | `main+0x03B4E300` |
| Caller `main+0x006E70F8` | **8 of 8 hits** |
| Alternate caller `main+0x006E6DD8` | **0 of 8 observed** |
| Incoming `S0` | **1.0 at all 8 hits** |
| Frame-step `S8` | **1.0 at all 8 hits** |
| Integer FPS target `X19+0xA8 -> manager+0x20 -> +0x2C8` | **60 at all 8 hits** |
| `frame_context+0xD38` flags | **0x0B at all 8 hits** |
| `frame_context+0xD50` integer counter | **4579, 4580, ... 4586**, increment 1 per observed hit |

The traced `X21` register cannot be trusted at this call site because
the original caller repurposes it after the original divide; the probe
correctly recovers FPS-state through the independently verified
`X19+0xA8 -> manager+0x20` chain.

**Supported conclusion:** In this eight-hit sample of the unpatched
~30 FPS gameplay state, the **later** `main+0x006E70F8` branch is
actually taken and feeds `S8=1.0` into the timing-config converter.
The `+0xD50` count increased by exactly one between these hits,
strongly connecting this branch to the earlier sparse
`+0xD50/+0xD58` observations (both counters moved together near the
~30 FPS overlay rate). We have not independently verified the exact
per-present physics update count.

It is **not** proven that the earlier callsite never executes in menus,
scene transitions or other flags/branches. With only eight breakpoint
hits, no unbiased runtime event rates or whole-frame timing ratios are
available. The saved flags `0x0B` differ by bit 5 from the earlier
sparse `0x2B` state, but that is **correlation**, not a confirmed
meaning for the flag or a proof of the alternate branch's trigger.

## New static-plus-math compatibility concern for V9

V9 has **three separate modifications**, not only a frame-step formula:
(1) it bypasses a frame-rate guard at E0F3 `main+0x03B4EF90`,
(2) changes the presentation argument at `main+0x03B4F080`,
and (3) replaces the original `FDIV` at `main+0x006E6CC4`
with its counter-based `S8` computation. The original branch we
just observed feeds `S8` to `main+0x03B4E300`, a routine that
translates positive step to a **rounded integer `60/step`**
and stores this nominal rate at `config+0x1C`.

Mathematically, if V9 receives the same *fresh* delta distribution
previously captured from the unpatched game:

- At ~50 displayed FPS, the predicted rounded derived rates from five
  timer samples are **50, 44, 46, 43, 44**.
- At ~30 displayed FPS, predicted rates are **32, 31, 29, 30, 28**.

**Nine of those ten values do not divide 60 evenly.** A separate verified
general FPS setter in this game *rejects* non-divisors of 60 and suggests
lower divisors. Whether the `config+0x1C` rate actually reaches that
setter in a given runtime state is **NOT proven**; do not assert it does.
This means arbitrarily fractional step ratios could encounter native
rate-validation or callback constraints, and is a reason to inspect
timing-config consumers before proposing V10.

Predicted rates are only **offline calculations from unpatched captures**.
The V9 patched game has **not** been instrumented, so its actual input
`+0x100`, live `S8`, generated rate and failure mechanism are unknown.
Do not pretend this experiment independently diagnoses V9's too-fast
gameplay; it only narrows live path identity and exposes a compatibility
risk.

## Next development focus

**Do not repeat an eight-hit baseline branch trace**; it answered its
question. Prioritize a source-only dependency audit of what consumes
`config+0x1C` and of the frame-rate controller/presentation guard paths.
Only after these connections are established should a controlled,
backup-protected patch experiment be considered. A useful design
may require keeping a stable supported native interval/presentation
configuration while separately accumulating elapsed real time for
simulation—but this is a proposal, not a verified implementation.

The previous 30/50 FPS timer captures and 30 FPS accumulator snapshots
remain the baseline. Both E0F3 and 33FA must ultimately be validated;
nothing in this E0F3 trace proves equivalent base-build offsets. Keep
stable `main`, releases and original game dumps unchanged.
