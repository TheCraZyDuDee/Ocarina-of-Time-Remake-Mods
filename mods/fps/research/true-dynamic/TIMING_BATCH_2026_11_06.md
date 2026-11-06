# E0F3 9,216-byte batch analysis — callback is a genuine step consumer

**Source-only research, 2026-11-06. No experimental IPS or release yet.**

The tester supplied private `timing_batch_private.json` from the
one-shot original E0F3 GDB capture. All three requested original-code
windows passed SHA-256 validation locally:

| Function | E0F3 main offset | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Original optional timing callback | `0x02F52DF0` | 4,096 | `9336fa4d83b2e97ddc867ebab4cf00a14eaf76411b478f9910c9f5d4f6b13e1d` |
| Presentation / interval setter | `0x0346C5C0` | 2,560 | `75b71e03048f238be0fc3e9da34c398a9df34e4e92355f1252e6da1725847443` |
| Shared FPS setter | `0x004DC0F0` | 2,560 | `8b6e744c9f099f5d0c725887d75fb5cfff0f87d973aefeb4a26511d3f9ebc664` |

The callback prefix also matches the prior separate 128-byte
SHA-256-verified capture. **No private instruction words, full
disassemblies, compressed NSOs, game saves or logs have been published.**

## 1. Callback definitely consumes the variable simulation step

The original virtual callback at `main+0x02F52DF0` is NOT merely
a pass-through that forwards `60/step` to the native FPS setter.
It has extensive per-object iteration, state-transition, interpolation
and aggregate-result logic.

At **`main+0x02F531E4`** it reads the **float step at
`config+0x10`** (the same field written by timing converter
`main+0x03B4E300` from `S8`). It then uses the step to:

- Numerically truncate / round step for **per-object integer countdown
  adjustments** at `main+0x02F53268..+0x02F53298`.
- Advance multiple float-valued interpolation accumulators using
  **FMADD with the step** on a conditional object-state path at
  `main+0x02F532B0..+0x02F53308`.
- Normalize a set of positive per-object scales by dividing by the
  step at `main+0x02F53444` onward, also guarded by flags and state.
- Write aggregated float results back into the passed config object,
  including `config+0x144/+0x14C/+0x154/+0x15C/+0x164/+0x16C/+0x174`.

For positive finite steps, there is source evidence that **some**
per-object updates are explicitly designed to respond to non-unit
steps, including fractional values. That is supportive for exploring
variable-step simulation, **but not proof that the entire engine's
physics, audio, collision, animation or menu clocks are all correct
at arbitrary steps.** The callback's exact gameplay object types
have not been independently identified.

A static scan of direct `BL` destinations in this 4 KB callback
window finds **no direct call to `main+0x004DC0F0` or
`main+0x0346C5C0`**. Other direct callees and indirect dispatches
exist. It is therefore **not proven** that the callback directly
reconfigures the native FPS/presentation controls. Do not repeat
the earlier assumption that non-divisor FPS rates necessarily flow
through this callback to the native validator.

## 2. Presentation setter changes an FPS-state field too

The original E0F3 `main+0x0346C5C0` function takes a timing
object in `X0` and an unsigned interval in `W1`.
It passes the interval into a lower-level setter at
`main+0x00F49970`, **then** executes:

- `W8 = 60`;
- `if (interval != 0) W8 = 60 / interval` (integer unsigned division);
- **`STR W8,[timing+0xFC]` at `main+0x0346C5EC`**.

Therefore the failed V9's forced presentation argument of **1**
also forces this timing object's `+0xFC` to **60**, even if
the persistent controller interval `controller+0x48` is different.
The source of original cached frame-tick delta `timing+0x100`
is a *different* counter/timestamp writer; these two fields must not
be conflated.

This strengthens the specific V9 mismatch: its frame-rate setter
is fed a rate derived from the controller's stored interval, while
its presentation setter forces interval 1 and writes a corresponding
60 rate into the timing state. A divergence **requires** stored
interval != 1; the failed V9 runtime interval was never recorded.

## 3. Shared FPS setter's divisor rule has an exception

At `main+0x004DC0F0` the shared setter ordinarily requires a
positive FPS request that divides 60 exactly, and has a rejected-rate
fallback suggestion when supplied an output pointer.

However a separate path is visible: if a state byte at `+0x231`
is 1, the FPS request is **at least 40**, and a bit of state
`+0x232` is set, it can handle the request in a special branch
at `main+0x004DC130..+0x004DC168` without the ordinary
divisor-of-60 test. The preconditions, semantics and generality
of this path are not yet independently verified.

**Correct earlier overgeneralization:** do not say the entire engine
unconditionally rejects all non-divisors. This native setter has
a special path, and (more importantly) we have not established
that the timing converter's rounded `60/S8` is always sent to it.

## Implication for an experimental first build

The user's explicit requested end product is a **genuine dynamic-FPS
mod that preserves real-time gameplay when rendered FPS drops**, not
a mod that happens to raise displayed FPS or globally speed up the game.

A defensible *first research candidate*, for later play testing,
is to **isolate the original frame-step hook's wall-clock scaling**
while **leaving both interval-controller sites unmodified**:

1. Do not replace `main+0x03B4EF90` (preserve original guard).
2. Do not replace `main+0x03B4F080` (preserve original interval).
3. Only replace the verified `main+0x006E6CC4` `FDIV S8`
   with a guarded, register-preserving private code-cave trampoline
   computing a bounded step from the original frame-like delta.
4. Verify source opcodes, build identity, code-cave isolation, branch
   targets and output IPS hashes. Do **not** claim gameplay validation
   until user tests game-time/animation/collision in 30 and 15 FPS
   scenes, menus and scene transitions with 100% emulator speed.
5. Never distribute an unvalidated combined patch as the final V10
   or publish user-owned proprietary code. Keep first builds only
   on the research branch or as private test artifacts.

This is an **experimental design**, not a proven fix. The observed
V9 excessive speed may depend on interactions with guard and
presentation changes; the isolated-step candidate can test that
hypothesis without carrying over the two unrelated V9 edits.
Base 33FA still needs an independently grounded downstream map
before claiming cross-build equivalence.
