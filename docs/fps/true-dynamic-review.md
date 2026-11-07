# True Dynamic FPS review

Reviewed on 2026-11-07 against the published E0F3 V10 patch.

The recommendation is to keep the current IPS. The helper is small, and this review didn't establish a gameplay bug or a measurable performance improvement worth replacing the tested release for.

## What the helper costs

One pass executes 20 ARM64 instructions in place of the original single divide: 16 helper instructions and four direct branches. It has no loop, allocation, logging, system call or per-frame patch installation. It reads three pointers/fields, saves and restores two registers, reads `CNTFRQ_EL0` once, computes the step and clamps it.

That suggests low overhead per invocation, but it isn't a benchmark. The hook's invocation rate and Eglantine's handling of the system-register read, memory accesses and translated blocks haven't been profiled. There is no defensible percentage or zero-impact claim from instruction count alone. The original instruction was already a floating-point divide; the helper still uses one divide.

## Execution checks

`tools/audit_dynamic.py` loads the actual IPS from the committed ZIP into Unicorn's ARM64 emulator with synthetic timing objects. It doesn't run a copy of the formula instead of the machine code.

The checks cover:

- Frame durations corresponding to 15, 20, 30, 45, 60, 90 and 120 FPS.
- Zero, negative and extreme signed tick counts.
- Counter frequencies of 19.2 MHz, 31.25 MHz and 1 GHz.
- One hundred repeatable random positive durations against the bounded timing formula.
- Return to the original instruction stream, 20 executed instructions, stack restoration, general registers, condition flags and unchanged vector registers outside V0/V8.
- Writes limited to the two expected stack slots in this synthetic execution.

All five audit tests passed. A temporary mutation replacing the lower maximum clamp with a minimum was caught by the tests. The existing six release tests also passed, including the pinned patch hash and byte-identical archives.

These checks validate the isolated helper under Unicorn's default floating-point environment. They don't measure performance, validate Eglantine's translator, verify original code-cave availability again, or establish correct timing throughout the game.

## Details to watch

| Finding | Meaning |
| --- | --- |
| The input duration is cached game state. | The helper doesn't know whether the producer updated it for this invocation. Research identified a conditional writer; freshness through pauses and scene changes still needs runtime evidence. |
| The step is clamped to 0.5–4.0. | This bounds extreme steps. Removing the cap could increase collision and animation problems; raising it isn't a free improvement. |
| D0 is restored, rather than the full Q0 register. | The low 64 bits survive, while the upper 64 bits of V0 are cleared. The captured source in the current repository doesn't establish whether those bits are live after the hook. This is a preservation limitation, not a demonstrated gameplay failure. |
| Negative signed durations clamp to 0.5. | This prevents a negative simulation step but doesn't recover missing elapsed time. |

The lower clamp also prevents steps below 0.5, so the formula cannot keep scaling down indefinitely at very high update rates. The relationship between update frequency and the rendered-FPS overlay is still unmeasured.

## Optimization options

- **Fewer trampoline branches:** would require a sufficiently large contiguous, verified code cave. The current three regions were verified during the original research; a larger unused region isn't established by this repository.
- **Cache or hardcode the counter frequency:** might avoid the system-register read, but introduces assumptions or state. Profile the actual emulator first; the read might already be inexpensive there.
- **Change division to multiplication:** requires a trustworthy reciprocal and attention to rounding. Since the original hook already divides, a speculative rewrite has a weak case without a measured benefit.
- **Preserve full Q0:** worth checking against the original surrounding code if a new patch is developed. It would need its own machine-code tests and playtest, rather than silently replacing the known-working IPS.

The most useful next measurement is a sparse count/profile of hook invocations and timing-field freshness during ordinary gameplay, pause/resume and scene transitions. Avoid a breakpoint on every update when assessing frame time: debugger pauses change the timing being measured.

## Run the audit

The regular build and release tests still need only Python's standard library. This additional check has one optional development dependency:

```sh
python3 -m pip install unicorn==2.1.4
python3 tools/audit_dynamic.py -v
```

CI runs the audit in a separate job. No game files, keys or live emulator connection are needed.

[Implementation notes](true-dynamic.md) · [AI research handoff](../ai/fps/true-dynamic.md)
