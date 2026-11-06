# E0F3 timing configuration path identity — temporary GDB breakpoints

**Not a dynamic FPS patch, not an unbiased timing benchmark.**
Unlike a pure memory read, GDB software breakpoints may temporarily
replace instructions in guest memory while armed; they are removed by
the helper. They are not a persistent mod and must never be used as
an elapsed-frame timing measurement.
Use this only to determine whether the normal-gameplay frame-step machinery
reaches either or both verified E0F3 timing-config calls into
`main+0x03B4E300`. The two original call sites are:

- `main+0x006E6DD8` (original ARM64 branch word verified)
- `main+0x006E70F8` (original ARM64 branch word verified)

The diagnostic [`guest_frame_step_path_trace.py`](guest_frame_step_path_trace.py)
checks the unmodified `fdiv` and both original callsite instructions,
installs two **temporary GDB software breakpoints**, records the code-site
identity, live `S0/S8` inputs, frame flags/counter and integer target FPS,
single-steps the original call, removes the breakpoints and resumes the game.
**Breakpoint interruptions disturb frame time**: do not infer real FPS,
frame duration, simulation event frequency, or game-speed ratios from hit
timestamps. Only callsite presence and register provenance are the goal.
The output is numeric-only with no copyright code instructions, but
keep your local debug output private.

A static scan of the first frame-step window established that `X21`
is repurposed as a different global pointer before the first callsite;
do **not** read the target FPS from `X21+0x2C8` at that point.
The diagnostic recovers FPS state through the verified
`X19+0xA8 -> manager+0x20` pointer chain.

## Run on the user's CachyOS/Eglantine

Keep `guest_timer_probe.py` in the same local directory as the new
`guest_frame_step_path_trace.py`. Restart the emulator, enable the
GDB stub on **port 6543**, disable all other FPS mods and keep speed at
100%. Back up saves before debugging. Start at the initial guest debugger
halt, then run the script below:

```bash
python3 guest_frame_step_path_trace.py \
  --log '/mnt/EmuStuff/Emulatoren/Switch 2/user/log/eden_log.txt' \
  --hits 8 \
  --output frame_step_paths_30fps.json
```

Use the actual current-session log path. The script resumes the game
and prompts to reach gameplay. Load your known ~30 FPS scene and press
Enter in the terminal. It collects up to eight visits to either
timing-config callsite, clearing breakpoints and resuming the guest on
normal completion or errors. This may cause a few visible pauses.
Do not run a concurrent debugger client.

If the preflight fails, **do not bypass the original-opcode check**.
Report the exact error; restart Eglantine if it does not resume.
Upload only `frame_step_paths_30fps.json` privately in chat.
Do not create or install V10 on the basis of this experiment.

Source-only synthetic protocol tests are in
`tests/test_guest_frame_step_path_trace.py`; all regression checks
passed in the latest Github Actions run on the research branch.
Current live Eglantine behavior is still **unverified**.
