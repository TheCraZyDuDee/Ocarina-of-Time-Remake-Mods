# E0F3 timer writer — first private instruction-window analysis (2026-11-06)

**Research only. This is not an FPS mod, and the measured clock's semantics are not yet proven.**

A private 640-byte GDB code-window read (`writer_opcode_window.json`) was
checked against its SHA-256 and exact 160-word length. The source window
begins at `main+0x0346C5EC`, and word index 128 identifies
`main+0x0346C7EC` as a real 64-bit store.

Disassembly identifies this sequence:

- `main+0x0346C7E0`: call a timing-related function
- `main+0x0346C7E4`: load previous reading from `[x19+0x108]`
- `main+0x0346C7E8`: calculate `x8 = x0 - x8`
- `main+0x0346C7EC`: store `x8` to `[x19+0x100]`
- `main+0x0346C7F0`: call the same timing-related function again
- `main+0x0346C7F4`: store returned `x0` into `[x19+0x108]`

The two direct calls in this sequence target `main+0x03C41FD0`, determined
from AArch64 PC-relative BL offsets. An earlier path also computes
`x0 - [x19+0x108]` and stores it at `[x19+0x148]`. The `+0x100` update is
**conditional** on flags, a threshold comparison, and a synchronization
state; it is unsafe to assume it occurs once per presented frame.

**Supported conclusion:** this writer uses a *difference of two readings*,
not a simple incrementing absolute timestamp. However, it has not been
established what the timer function returns, what clock units it uses, whether
the window measures a whole displayed frame, or whether `x19` in this
function is the same object as `x21` at the frame-step division. Previous
watchpoint results make that association plausible but do not prove complete
object provenance. V9's gameplay failure is unchanged; **do not create V10
from this finding alone**.

## Next read-only capture

Use [`guest_timer_source_window.py`](guest_timer_source_window.py) alongside
[`guest_timer_probe.py`](guest_timer_probe.py) on the tester's private Linux
system. The program refuses an unknown build or mismatched original opcodes,
reads only 384 bytes at `main+0x03C41FD0`, and resumes the game. It does not
install any patch or set debugger breakpoints. The produced JSON contains
private original game instruction words and **must never be committed**.

Start Eglantine with GDB stub enabled, all FPS mods disabled, and the game
stopped at initial debug attach. Then run:

```bash
python3 guest_timer_source_window.py \
  --log '/mnt/EmuStuff/Emulatoren/Switch 2/user/log/eden_log.txt' \
  --output timer_source_window.json
```

Use the actual *current session* log path. Privately supply the JSON for
inspection, not GitHub. A synthetic test is in
`tests/test_guest_timer_source_window.py`. No proprietary instruction words
from the captured JSON are reproduced here.

After identifying the source clock, verify end-to-end measurement lifecycle
and scheduling during uninterrupted gameplay, menus and scene changes before
considering a new IPS patch.
