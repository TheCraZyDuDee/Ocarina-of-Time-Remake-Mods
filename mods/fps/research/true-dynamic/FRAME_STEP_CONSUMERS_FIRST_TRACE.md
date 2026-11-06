# E0F3 frame-step function: first downstream consumer trace (2026-11-06)

**Scope: privately captured original E0F3 ARM64 code, statically disassembled. NOT a V10 mod.**

The tester supplied `frame_step_window.json`, covering a bounded 1,024-byte original-code
window from `main+0x006E6BE0` through `main+0x006E6FDC`, with 256
little-endian AArch64 instruction words. The SHA-256 matched the capture.
All seven original opcode fingerprints used by the read-only capture tool
matched. **No captured Nintendo instruction window is published.**

## Correction: exact target-FPS integer-to-float dataflow

The earlier `+0x2C8` raw `0x3c` / integer 60 observation
and the live `s0=60.0` gameplay observation are now directly reconciled
by static instructions:

- `main+0x006E6C98`: `LDR S0,[X21,#0x2C8]`; **the raw 32 bits are integer data**, not an already-encoded float.
- `main+0x006E6CA8`: `SCVTF S0,S0`; reinterpret that register's
  low 32 bits as a signed integer and **numerically convert to float32**.
- `main+0x006E6CC0`: `FCSEL S1,S1,S2,EQ` selects a nominal base
  rate of **60.0 or 30.0**.
- `main+0x006E6CC4`: `FDIV S8,S1,S0` produces the original
  simulation-step factor, seen as **1.0** for live E0F3 gameplay at
  actual sub-60 FPS when `S0=S1=60.0`.

The user's observed unpatched game behavior is **slow motion below 60
actual FPS**. This is consistent with insufficient game-time advancement
from a fixed step; static instructions alone do not prove every update
fires exactly once per presented frame.

## Verified downstream dataflow (conditional paths)

After the `FDIV`, the function checks object flags. On a path gated
by its atomically updated `frame_context+0xD50` counter, it:

1. Converts `S8` to double (`FCVT D1,S8`) and adds it to the
   double-precision accumulator at `frame_context+0xD58`.
2. Stores the resulting double bits back to `+0xD58` (or zero on
   a separate sentinel-counter branch).
3. Copies `S8` to the incoming `S0` argument and calls
   **`main+0x03B4E300`**, using a globally sourced pointer in
   `X0` (loaded earlier into `X20`).

At the beginning of this region, `TBNZ W9,#1` also diverts to
another execution path; some code targets and later joins fall
**outside** the supplied 1,024-byte window. Therefore the accumulator
and call are not proven to execute on every game update.

The call to `main+0x03B4E300` and double accumulator provide concrete
consumers of the `S8` simulation multiplier. The callee's semantics,
update order relative to `+0x100` counter refresh, scene-change
behavior, and the exact number of updates per displayed frame remain
unverified. **Do not assume the multiplier alone fixes all physics.**

## Next private read-only capture

[`guest_frame_step_followup.py`](guest_frame_step_followup.py)
verifies the original frame-step divide plus five discovered source
opcodes before capturing two bounded code windows:

- `main+0x03B4E300`: 1,536 bytes of the direct downstream callee;
- `main+0x006E6FE0`: 1,792 bytes continuing the original frame-step
  function beyond the preceding capture.

No injection, FPS IPS, breakpoint, watchpoint, or game-memory write is
performed. Both source windows contain copyrighted instruction words:
**the resulting JSON is private and must never be committed**.
The tool has synthetic guard tests
[`tests/test_guest_frame_step_followup.py`](../../../../tests/test_guest_frame_step_followup.py).
It has not yet been validated against the live tester emulator.

On Eglantine with GDB port 6543 enabled and all FPS mods disabled,
restart and launch the game to its **initial debugger halt**. Keep
`guest_timer_probe.py` alongside the downloaded follow-up tool.
Run with the *current-session* log file:

```bash
python3 guest_frame_step_followup.py \
  --log '/mnt/EmuStuff/Emulatoren/Switch 2/user/log/eden_log.txt' \
  --output frame_step_followup.json
```

No loaded save or FPS benchmarking is needed: this is static code
inspection. The script attempts to resume the game even on errors.
Privately supply `frame_step_followup.json` for the next analysis.
Do not build V10 from the static partial dataflow alone; first establish
the callee's role, frame-update cadence and timing state lifecycle.
Base 33FA still needs independently verified offsets.
