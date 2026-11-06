# E0F3 frame-step callee + caller continuation — private static analysis (2026-11-06)

**Status: new dataflow evidence; V9 failed and no validated V10 exists.**

A tester provided `frame_step_followup.json`, two code windows from the
**unmodified E0F3 game**. Both private SHA-256 fingerprints matched:

- `main+0x03B4E300`, 1,536 bytes, 384 original AArch64 words;
- `main+0x006E6FE0`, 1,792 bytes, 448 original AArch64 words.

Both were decoded as AArch64; combining the second region with the
previously verified `main+0x006E6BE0` window gives a contiguous
caller excerpt through `main+0x006E76DC`.

The code words and private guest addresses are **not published**. Only
structural conclusions, small opcode fingerprints and offsets belong
on this research branch.

## The callee translates time-step to a frame-rate configuration

The direct target `main+0x03B4E300` receives a float in `S0`,
transferred from the caller's `S8` at `main+0x006E6DCC`
(or `main+0x006E70EC` on another path).

Early in the callee:

- `main+0x03B4E32C`: `FDIV S1,S1,S0` with S1 first initialized
  to `1.0f`, giving the reciprocal of the incoming time step.
- `main+0x03B4E330`: stores the incoming step and its reciprocal
  as float32 at `config+0x10` and `config+0x14`.
- `main+0x03B4E334` / `+0x338`: multiplies the step by an
  external float constant and stores the result at `config+0x18`.
  That constant's value and meaning were not captured.
- `main+0x03B4E340`: computes `60.0f / step`.
  The following instructions truncate to integer, compare with
  fractional thresholds around ±0.5 and adjust rounding;
  `main+0x03B4E368` stores the resulting integer in
  **`config+0x1C`**.
- The function then propagates various related timing ratios through
  the config object (e.g. base, reciprocal, scaled, 60/base).
  Multiple fields and optional callback paths are involved.
  Their precise gameplay consumers remain unverified.

For *positive finite* steps far from rounding thresholds, this maps
input 1.0 to 60, 1.5 to 40, 2.0 to 30, 3.0 to 20 and 4.0 to 15.
**Do not claim arbitrary fractional values are accepted by every
downstream game rate validator or simulation subsystem.**

This is a **timing-configuration update**, not visible evidence that
the callee executes N fixed physics substeps.

## Two caller sites / accumulator paths

The full E0F3 frame-step code includes **two BL instructions** to the
same `main+0x03B4E300` routine:

- `main+0x006E6DD8`
- `main+0x006E70F8`

Both are reached through conditions involving `frame_context+0xD38`
flags and additional branches. Preceding each call is a path that
converts `S8` to double precision and adds it to a double-precision
counter at `frame_context+0xD58`. An atomic counter at
`frame_context+0xD50` is also updated.

**Important:** two *static* call sites are not proof of two physical
updates per frame, and even an increment to `+0xD58` is not itself
proof of a physics substep. Some execution paths may reach both calls;
their live frequencies and update ordering are unknown. The code
also changes state flags and dispatches through additional callbacks.
Treat this as a candidate contributor to V9's over-speed, not a
verified failure explanation.

The unmodified game is known from the tester's direct observation to
**run in slow motion whenever actual render performance is below
60 FPS**. V9, by contrast, accelerated gameplay near 30 FPS. Earlier
sparse physical-counter evidence shows a plausible `+0x100`
delta of ~33 ms at natural ~30 FPS (not a universal four-tick clamp).
These observations do not establish the number of updates per present.

## Next numeric, sparse state probe (no IPS)

The new independently authored
[`guest_frame_step_cadence_probe.py`](guest_frame_step_cadence_probe.py)
uses the Eglantine GDB stub to identify the live original frame
context `X19`, integer target FPS state `X21`, and the timing
configuration `X20` at the verified unmodified `fdiv` hook.
It checks both the context→state pointer chain and the original
global→config pointer chain, removes the temporary breakpoint,
single-steps the original instruction, and resumes guest execution
for several seconds between sparse *numeric-only* snapshots.

It records: the `+0xD58` double accumulator, `+0xD50` counter
and `+0xD38` flags; callee-generated `config+0x10/+0x14/+0x18/+0x1C`
values; the integer target FPS at `X21+0x2C8`; and cached physical
counter values `X21+0x100/+0x108`. It reports accumulator change per
guest-counter second **only when an uninterrupted finite accumulator
difference can be computed**. The value is not labeled as an actual
physics-update count. Scene transitions can invalidate the pointers
and cause the tool to stop rather than infer new state.

The tool is research-only; it does not patch game memory. Its synthetic
tests validate fake debugger reads and the cleanup path. It has **not**
been executed against the tester's current Eglantine build.

First run at ordinary gameplay ~30 FPS (FPS mods off, 100% speed);
a second run at ~50 FPS can be helpful for comparison if needed. For
each run, restart Eglantine and use a distinct output filename.
From the local folder containing `guest_timer_probe.py` and
`guest_frame_step_cadence_probe.py`:

```bash
python3 guest_frame_step_cadence_probe.py \
  --log '/mnt/EmuStuff/Emulatoren/Switch 2/user/log/eden_log.txt' \
  --fps-label 'about 30 fps' \
  --samples 5 --seconds-between 4 \
  --output frame_step_cadence_30fps.json
```

At initial GDB halt, execute the script; it resumes the guest. Load a
stable gameplay scene and press Enter in the terminal. The FPS label
is only user observation, **not** a script measurement.
If pointer checks or hook verification fail, do not disable guards.
Upload only the private numeric JSON here for analysis; do not publish.

Only then assess whether the accumulator reflects frame/update cadence.
A trace of **true per-present** and **per-physics-update** call counts
would ideally require a separate verified emulator-side instrumentation
path. No new installable dynamic IPS is justified yet.
