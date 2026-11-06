# V9 interval-controller original branch: verified target and next bounded audit

**Source-only investigation, 2026-11-06. No V10 patch or release.**

This audit uses the archived V9 builder's independently verified original
E0F3 fingerprints and the already documented active frame-step path.

At E0F3 `main+0x03B4EF90`, the original instruction
`TBNZ W8,#0, main+0x03B4F074` has an exact 14-bit branch
displacement of **+0xE4 (228 bytes)**. V9 replaced this instruction with
`NOP`, so it **unconditionally falls through** into a region the
original code sometimes skips. The target lies **12 bytes before**
the presentation-argument load at `main+0x03B4F080`.

At E0F3 `main+0x03B4F080`, original
`LDR W1,[X20,#0x48]` was independently replaced by
`MOV W1,#1`. These V9 changes can affect both **which controller
work executes** and **which presentation argument is passed**, on top
of the separate `FDIV S8` timing-hook replacement. Without the
original code around the 228-byte guarded region, we do not yet
know exactly what it does or how the forced fallthrough changes
presentation callback behavior.

Therefore the user-observed V9 too-fast game cannot be diagnosed
solely from its 31.25 MHz elapsed-time conversion. The two presentation
and guard changes are plausible co-causes and must be isolated.

## Prepared source-window diagnostic

The branch now includes the guarded, read-only
[`guest_v9_controller_window.py`](guest_v9_controller_window.py)
plus synthetic tests in `tests/test_guest_v9_controller_window.py`.

For updated E0F3 only, it checks the original unpatched frame-step
hook and the exact guard/presentation instruction fingerprints,
then reads a **2,048-byte** contiguous original-code region
`main+0x03B4EE80..main+0x03B4F67F`. It sets no breakpoints
and modifies no game memory. The resulting private JSON contains
copyrighted original code and **must not be committed to GitHub**.

This is an opt-in capture prepared for a later moment when live
emulator access is available. Do **not** request another baseline
FPS timer run or immediately reenable V9. The new capture's specific
purpose is control/dataflow identification of the guard's skipped
region and the presentation call's value. It is not an FPS benchmark.

From the user's directory containing `guest_timer_probe.py`
and the newly downloaded inspector, restart Eglantine with GDB enabled
on port 6543, disable FPS patches, and start the guest at its initial
debugger stop. No save load is needed.

```bash
python3 guest_v9_controller_window.py \
  --log '/mnt/EmuStuff/Emulatoren/Switch 2/user/log/eden_log.txt' \
  --output v9_controller_original.json
```

Use the actual current-session log path. The tool resumes the guest.
The resulting JSON should only be shared privately in chat.
Do not bypass mismatch guards; if the build or original instructions
do not match, stop. No complete mod is claimed.

## Offline work limit

The two user-supplied private NSO files are still in ZBIC-compressed
format. Stock `zstd` cannot decode the modified ZBIC entropy tables:
it requires a ZBIC-aware decompressor. The existing private
`private_nso_inspection_image.py` verifies original NSO segment
hashes if the independently licensed `zbic` package is installed.
No proprietary game code has been committed and no compressed dump is
redistributed. Disassembly from prior 1024/1792-byte private
frame-step windows is available locally for the adjacent simulation
path, **not** for the V9 guard's 228-byte control region.
