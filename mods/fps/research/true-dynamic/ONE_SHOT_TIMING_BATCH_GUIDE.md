# Faster research protocol: capture three E0F3 source functions in one run

**2026-11-06 — reduces repeated emulator restarts and user uploads.**

## Why this replaces the previous tiny capture requests

The tester's private `config_callback_target.json` confirmed:

- E0F3 original timing configuration **step=1.0**, **nominal=60**;
- The optional `config+0x1C8` callback **is non-null** in the
  observed gameplay scene;
- Its virtual method resolves to **`main+0x02F52DF0`**;
- The captured first **128 bytes** matched SHA-256
  `e138ddb9b69b7b8d9c8db9443980261995f0efe24586d0e11111bc24727f6a50`.

The function begins by reading and checking additional global state,
and some direct branches extend **past the 128-byte excerpt**.
It is therefore **not proven** that this callback calls the native
FPS or presentation setter, even though its object is present.

The newest
[`guest_timing_batch_capture.py`](guest_timing_batch_capture.py)
reads these three **original functions in one GDB session**:

| Function | Main offset | Original bytes |
| --- | --- | ---: |
| Verified dynamic timing callback | `main+0x02F52DF0` | 4,096 |
| Native presentation/swap setter | `main+0x0346C5C0` | 2,560 |
| Native shared FPS setter | `main+0x004DC0F0` | 2,560 |

Total **9,216 original-code bytes**, captured into **one JSON**.
The tool guards the original frame-step opcode and four exact native
controller instructions, verifies both direct call destinations,
and checks the callback's first 128-byte SHA-256 against the
previously supplied private live capture. It aborts on mismatches
and does not work on the 33FA game build. Captures do not use
breakpoints, watchpoints, timing patches, or writes.

**The output JSON contains proprietary original code. Do not commit
it to GitHub or share it publicly.** Only research notes, synthetic
tools and numerical/structural conclusions may be published.

## One-time user procedure

Download the new tool once to the local directory already containing
`guest_timer_probe.py`:

```bash
cd "/home/l/Schreibtisch/Neuer Ordner"
curl -fL 'https://raw.githubusercontent.com/TheCraZyDuDee/Ocarina-of-Time-Remake-Mods/research/true-dynamic-fps/mods/fps/research/true-dynamic/guest_timing_batch_capture.py' -o guest_timing_batch_capture.py
```

Disable **all FPS patches**, enable the Eglantine GDB stub at port
**6543**, restart the emulator, and launch the game to the **initial
debugger stop**. **No save or gameplay loading is required** for this
static original-code inspection.

```bash
python3 guest_timing_batch_capture.py \
  --log '/mnt/EmuStuff/Emulatoren/Switch 2/user/log/eden_log.txt' \
  --output timing_batch_private.json
```

Use the *current-session* log path. The tool resumes the game and
writes the single private file when it succeeds. Do not bypass an
opcode mismatch. Keep the raw file in the private conversation only.

Then offline disassembly can investigate the callback's full
control flow and its relationship to the native FPS/presentation
setters without another one-function-at-a-time GDB cycle.

## What it cannot do

This is a **source capture** and does not establish actual callback
call frequency, runtime FPS setter acceptance or physics advancement.
Further live diagnostics should be requested only when a new,
specific hypothesis demands them, and should **batch numeric probes
rather than repeatedly restart for one register or field**.

The test file `tests/test_guest_timing_batch_capture.py` uses only
synthetic mocked debugger responses. CI passed, but live Eglantine
behavior of this new combined script is not yet proven. Stable
`main` and all published release mods remain unchanged.
