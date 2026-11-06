# First live Eglantine write-watchpoint evidence (E0F3, 2026-11-06)

**Status: one code location observed on all 4 field writes. This is
a provenance lead, not yet a validated elapsed-time source for V10.**

The tester ran the opt-in `guest_timer_write_trace.py` while a save was
loaded into gameplay on the updated E0F3 executable. The original
frame-step hook was previously checked byte-for-byte. All four field
watchpoint hits targeted `x21+0x100` and reported exactly the same
game module PC:

> **`main+0x0346C7EC`** (E0F3 only; corresponding 33FA offset unknown).

The reported numeric values, converted **conditionally** with the
guest's documented 31,250,000 Hz counter frequency, are:

| Hit | Observed unsigned 64-bit value | Time if guest ticks |
| --- | ---: | ---: |
| 1 | 7,040,467 | ~225.3 ms |
| 2 | 19,138,755 | ~612.4 ms |
| 3 | 476,073 | ~15.23 ms |
| 4 | 1,263,539 | ~40.43 ms |

The initial cached field value was 7,040,467, equal to the first
watchpoint read. The values are **not cumulative/monotonic**.
At least two observations fall into the plausible duration range for
normal gameplay, despite the debugger's long interruptions.
The same PC on all four watchpoint events is **stronger evidence of a
specific producer** than the earlier GDB timer-value correlations.

## What this does and does NOT establish

- The debugger requested `Z2,<state+0x100>,8`, i.e. an 8-byte **write
  watchpoint** at the previously discovered live `x21` pointer.
  This is not a patch and did not bypass the opcode guard.
- The reported PC `main+0x0346C7EC` comes from Eglantine's GDB
  stop register set. Depending on watchpoint implementation, this
  may point to the store, an adjacent instruction, or a post-store PC.
  The **exact opcode is not yet read**.
- Field `+0x100` is plausibly a *frame-duration-like quantity*.
  The data do **not** yet prove its timebase, provenance, inclusion
  of renderer stalls/vsync, or when it is sampled relative to the
  frame-step `fdiv` and physics update.
- Its changing value during watchpoint testing is **not evidence**
  that V9 saturated, or that its source is correct at natural play
  speed. Previous V9 failure is still a measured gameplay outcome,
  with cause not fully identified.

## Follow-up: one no-breakpoint static instruction excerpt

The compressed original E0F3 game module is ZBIC, and we have not
decoded it in this analysis environment. The next safest step is
to read a **small 640-byte window** from the user's own guest
memory around the observed PC. It gives 160 AArch64 instruction
words: 128 before, 32 after the watchpoint stop address.
The window permits identifying the actual store, nearby timer
arithmetic and relevant branch/call patterns. It **does not run**
the game at modified speed or inject any patch.

The independently authored
[`guest_writer_static_window.py`](guest_writer_static_window.py)
runs at Eglantine's initial stopped debug state:
- validates E0F3's **unmodified** frame-step opcode;
- uses the **current-session** `eden_log.txt`, not a stale main base;
- reads only 4 bytes at the known hook and 640 bytes of code around
  `main+0x0346C7EC`;
- resumes the guest, saves `writer_opcode_window.json` locally.

**Caution:** Unlike prior numeric-only diagnostics, this JSON contains
a small excerpt of the user's copyrighted guest executable. It is
strictly for private analysis. **Do not commit the JSON, hex words,
or original NSOs to this public repository.** Keep only analysis,
original identifiers/offsets, and independent source/tool code.

This read-only helper has synthetic tests and repository CI but has
**not yet run on a real Eglantine session**.

Before designing V10, inspect the actual writer disassembly,
its input-clock semantics and full presentation cadence; determine
if `+0x100` supplies real completed-frame elapsed time or only a
partial CPU-time sample. The script's original read-only safeguards
must remain intact.
