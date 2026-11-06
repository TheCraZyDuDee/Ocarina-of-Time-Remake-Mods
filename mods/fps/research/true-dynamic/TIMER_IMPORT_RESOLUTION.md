# E0F3 timer import trampoline identified (2026-11-06)

**Source-derived finding; NOT a working FPS mod.**

The private 384-byte `timer_source_window.json` for the verified updated
E0F3 main executable passed its SHA-256 check (96 little-endian ARM64 words).
The first four instructions at `main+0x03C41FD0` are an AArch64 import
veneer: `ADRP X16`, `LDR X17,[X16,#0x1B0]`,
`ADD X16,X16,#0x1B0`, `BR X17`. ADRP's page-relative immediate
resolves to `main+0x04CBF000`, making the loaded pointer slot
**`main+0x04CBF1B0`**. This address is the location of the pointer,
NOT the destination implementation. No game instruction bytes or captured
code words are included here.

The 384-byte window consists of a repeating 16-byte veneer pattern
(not an implementation of a clock API). The previous writer code shows a
difference between returned time readings being written to
`[x19+0x100]`, and updates the previous-sample field `[x19+0x108]`.
The meaning, clock frequency, and whole-frame duration coverage remain
unknown. In particular, do not claim V9 is fixed or build V10 yet.

## Next read-only diagnostic

[`guest_timer_import_target.py`](guest_timer_import_target.py)
checks the original timing hook and four-instruction veneer, reads only
the 8-byte slot `main+0x04CBF1B0`, and reports the function pointer
as a private guest address. If the pointed-to address lies inside the
verified E0F3 main-module bounds, it also reads only 128 bytes of the
target's code for private analysis. Otherwise, it does NOT blindly
follow the pointer into an unknown module; a current session module
map will be necessary.

At the **initial stopped** Eglantine GDB session, with all FPS
mods disabled and the same directory containing
`guest_timer_probe.py`:

```sh
python3 guest_timer_import_target.py \
  --log '/mnt/EmuStuff/Emulatoren/Switch 2/user/log/eden_log.txt' \
  --output timer_import_target.json
```

Use your current-session log path. Upload the private JSON in chat, not
GitHub. The helper resumes the guest on its exit path. Synthetic guard
tests are in `tests/test_guest_timer_import_target.py`.

No executable/game bytes, keys, or collected private instruction words
may be committed. Keep stable `main` and published mods unchanged.
