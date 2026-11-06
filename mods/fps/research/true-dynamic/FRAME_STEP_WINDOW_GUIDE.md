# Next source-only experiment: E0F3 frame-step consumers

The 2026-11-06 E0F3 sparse timer captures at about 50 and 30 FPS
confirmed that the `X21+0x100` cached `CNTPCT_EL0` delta scales
approximately with real frame duration. See
[QUIET_GAMEPLAY_30FPS_TRACE.md](QUIET_GAMEPLAY_30FPS_TRACE.md).

**Do not rerun the same timer snapshots unless a new hypothesis needs testing.**
We need to understand the original simulation update's control/dataflow
before proposing V10. The known E0F3 `fdiv s8,s1,s0` is at
`main+0x006E6CC4`, inside a function with verified entry
`main+0x006E6BE0`. A new small read-only tool
[`guest_frame_step_static_window.py`](guest_frame_step_static_window.py)
captures **1,024 original instruction bytes** beginning at that entry,
including the division and subsequent instructions, while checking
seven exact original source fingerprints. It does not modify game code,
install any FPS patch, or set breakpoints. It resumes the debugger guest
on exit, even after an error.

This is **E0F3-only**; it deliberately rejects other build IDs. Five synthetic tests were added for the read bounds and failure guards;
local isolated capture tests passed, but the new repository test file has
not been run as part of the full CI suite, and the tool has not yet
run against the tester's emulator.
The resulting JSON includes **copyrighted game instruction words**:
keep it private and **never commit it to GitHub**.

## Tester procedure

With `guest_timer_probe.py` and the new
`guest_frame_step_static_window.py` in the same local folder, disable
all other FPS mods, enable Eglantine GDB Stub on port 6543 and restart
the emulator. Launch the game until it is **paused at its initial
debugger stop**; a save does *not* need to be loaded for this static
code inspection.

Use your real current-session `eden_log.txt` path:

```bash
python3 guest_frame_step_static_window.py \
  --log '/mnt/EmuStuff/Emulatoren/Switch 2/user/log/eden_log.txt' \
  --output frame_step_window.json
```

If the script reports a source-opcode mismatch, do **not** bypass the
check. Verify the correct main-module load base, E0F3 game build,
and absence of enabled executable patches. If the emulator does not
resume after a transport failure, restart it rather than blindly
re-running the script.

Privately supply only `frame_step_window.json` for analysis. The
capture should enable an initial static map of the `s8` consumers,
nearby calls and branch paths. It **cannot prove** actual call count
per rendered frame; that requires a subsequent independently checked
runtime measurement, potentially in emulator source or noninvasive
instrumentation. Do not build V10 until the consumers and timing
lifecycle are understood.
