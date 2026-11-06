# Physical-counter import resolved — E0F3 (2026-11-06)

**Status:** Timer *source and units* identified. Complete-frame cadence and V9 failure mechanism remain unverified. No new FPS IPS should be built yet.

## Observed private capture

The tester ran `guest_timer_import_target.py` after loading gameplay. The private `timer_import_target.json` reports build ID
`E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348`, import veneer
`main+0x03C41FD0`, pointer slot `main+0x04CBF1B0`, and an
*out-of-main* resolved guest address (address omitted here). All 64 little-endian
words of the 256-byte capture were independently checksum-verified. **Do not
commit the JSON, its guest address, or proprietary code words.**

The very first instruction at the resolved target is `MRS X0, CNTPCT_EL0`,
followed by `RET`. This is an ARM64 physical system-counter read.
A distinct nearby routine uses synchronization barriers around the same
counter read. Another nearby routine returns the immediate
`0x01DCD650` = **31,250,000**, consistent with the Switch 2 guest
counter frequency. The constant is strong corroboration, although it is
not proof that every game timing field necessarily uses this frequency.

## Dataflow established with the previous writer window

At E0F3 `main+0x0346C7E0`, the game calls the import through the
verified veneer, then at `+0x0346C7E4` reads `[X19+0x108]`,
at `+0x0346C7E8` subtracts it from the new timer reading, and at
`+0x0346C7EC` stores the difference to `[X19+0x100]`.
It then calls the clock a **second time** and updates
`[X19+0x108]` at `+0x0346C7F4`.

An earlier path computes another difference from the same previous
reading and writes `[X19+0x148]`. The `+0x100` store is **conditional**:
branches depend on object flags, a threshold and synchronization. It is
not safe to assume that every presented frame refreshes this field,
or that it includes GPU work, vblank or all simulation stages.

This confirms the producer of a **physical-counter tick difference**,
resolving the original unknown about its units. The live watchpoint on
the address obtained as `X21+0x100` fired at this writer, strongly
connecting the two pointer-relative views. What it does NOT prove is
that V9 sampled a fresh full-frame duration or that the game used it
without saturation under uninterrupted play.

V9 **still failed**: around 15 rendered FPS the game felt normal,
around 30 it ran too fast, and below 15 it slowed down. Paused debugger
samples cannot determine V9's uninterrupted clamp behavior.

## Next measurement

Capture sparse snapshots of `X21+0x100`, `+0x108`, `+0x148`, and
`+0x150` **after multiple seconds of free-running gameplay**, rather
than break on every writer call. First find the original X21 pointer at
the verified frame-step hook, remove the temporary breakpoint, step the
original instruction, let the guest run, then briefly interrupt to
read the fields. Check that the object's identity still matches.

Compare the duration-field magnitudes with independently observed FPS:
at 31.25 MHz, a full-frame 60/30/15 FPS interval would be around
520,833 / 1,041,667 / 2,083,333 counter ticks. The V9 four-tick upper
clamp at nominal 60 Hz begins around 2,083,333 ticks.

**Sparse snapshots are only evidence about the cached field**, not a
per-frame profiler, and interrupts can still affect the immediately
following frames. Keep all FPS patches off, refrain from installing a
new mod, and do not publish private raw captures. Investigate frame
dispatcher order, timer update cadence and physical simulation substeps
before creating a new IPS. Both E0F3 and base 33FA still need
build-specific static verification.
