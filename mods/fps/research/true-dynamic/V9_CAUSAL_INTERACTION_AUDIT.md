# V9 independent patch interaction audit and timing callback discovery

Research branch: `research/true-dynamic-fps` — 2026-11-06.

**The user's unmodified game slows below actual 60 FPS. V9 is a failed experiment,
not a verified dynamic-FPS mod. This is source-only analysis, not a new IPS.**

## V9 changes three distinct behaviors

The archived `real_elapsed_probe_builder.py` produces three modifications
on both E0F3 and 33FA; known offsets are module-relative and the original
opcodes are exact fingerprints (not copied proprietary code excerpts).

| Function | E0F3 main+ | Original semantic | V9 replacement |
| --- | --- | --- | --- |
| Interval-controller guard | 0x03B4EF90 | `TBNZ W8,#0, +0xE4` | `NOP`: always fall through |
| Presentation argument | 0x03B4F080 | `LDR W1,[X20,#0x48]` | `MOV W1,#1`: discard stored argument |
| Simulation-step math | 0x006E6CC4 | `FDIV S8,S1,S0` | Branch into V9 elapsed-tick / clamp helper |

For 33FA, the parallel source-verified patch offsets are
`0x03AF1920`, `0x03AF1A10`, and `0x006B5A08`. Detailed
callee and active-callsite runtime mapping is E0F3 **only**.
The presentation function's exact numerical argument interpretation,
and the guarded bit's intended phases, need independent verification;
the names above describe their *role in nearby controller code*, not a
proof of the guest's rendering behavior when modified.

**Critical confounder:** V9 changes presentation pacing, controller
branch selection, *and* time-step generation simultaneously. The
observed V9 over-speed cannot be causally assigned to any one of them.

## New static finding in original E0F3 timing-config callee

The user's earlier private `frame_step_followup.json` was disassembled
again around `main+0x03B4E300`. For ordinary finite positive inputs,
the callee:

- Stores incoming `S0` (time step) at `config+0x10`.
- Stores `1.0 / S0` at `config+0x14`.
- Uses `60.0 / S0`, rounded to an integer, to populate `config+0x1C`.
- At `main+0x03B4E364`, loads an *optional* callback pointer from
  `config+0x1C8`. At `main+0x03B4E368`, writes the new derived rate.
  Unless the callback pointer is zero, the code loads a virtual-table
  method at offset `+0x10` and calls it, passing the config object.

There is **no equality check against the previous config+0x1C rate**
on the visible path before that callback. Therefore, if the callback
object is present, it can be invoked every time the converter runs,
even when the numerical rate has not changed. This by itself does NOT
prove the callback changes presentation settings or FPS; its runtime
target is still unverified.

## Why the callback could matter to V9

The latest unmodified ~30 FPS gameplay breakpoint trace proved the
actual config caller is `main+0x006E70F8` on eight consecutive hits,
with `S8=S0=1.0`, target 60 and `+0xD50` counter increasing by one.

Using the original game timer data (NOT running V9), V9's hypothetical
step at ~30 FPS would be ~1.89–2.11. The converter would round 60/step
to values **32, 31, 29, 30, 28**, of which only 30 is an exact divisor
of 60. The earlier original ~50 FPS samples predict
**50, 44, 46, 43, 44**. A *separate* general FPS setter has been shown
to reject non-divisors of 60, but **we have not proved** the converter's
virtual callback reaches that setter. Do not conflate those APIs.

If this callback or another consumer applies each transient nominal
rate to native pacing, it could create a feedback loop, especially
alongside V9's forced presentation value 1 and disabled guard.
This is a **testable causal hypothesis**, not a diagnosis.

## Priorities before any experimental V10

1. Establish whether `config+0x1C8` callback is non-null in ordinary
   gameplay; resolve the actual virtual method pointer, then map its
   caller/callee roles without guessing object types.
2. Identify the *original* source of the interval-controller
   presentation value `[X20+0x48]`, and conditions controlled by the
   guard bit. Keep those controller decisions distinct from simulated
   time-step length.
3. Determine whether the config callback ultimately uses the native
   divisor-of-60 FPS setter; if it does not, revise that part of the
   hypothesis accordingly.
4. Plan controlled, isolated experiments that change **only one**
   of V9's three behaviors at a time; do not revive the known-failed
   combined V9 patch. Preserve its original registers, scenes/loading
   lifecycle, current-user saves and stable release mod packages.
5. Before publishing or promising V10, establish how physics substeps
   and game-time advancement are actually coupled to the timing config.

No new user captures are necessary to understand the *static* facts
above. Mapping the live callback object will eventually require a
small, verified read-only emulator observation or a complete private,
hash-verified E0F3 decompressed inspection image (the currently attached
NSOs are ZBIC-compressed). Do not publish game binaries or raw instruction
windows. The known-failed V9 cannot be recommended for gameplay.


## Subsequent batch correction: callback is a step consumer

The full original E0F3 source batch resolved the optional callback
at `main+0x02F52DF0`. It loads `config+0x10` step and performs
per-object integer countdown, interpolation and aggregate float
updates. There is no direct call to either FPS setter or
presentation setter in its verified 4096-byte code window.
The earlier suggestion that the callback specifically invokes the
native non-divisor FPS validator is **not supported** by this source
window. Other indirect dispatch remains possible. Separately, the
native FPS setter has a special >=40 path that bypasses its normal
divisor rule under additional state conditions. See
[TIMING_BATCH_2026_11_06.md](TIMING_BATCH_2026_11_06.md).
