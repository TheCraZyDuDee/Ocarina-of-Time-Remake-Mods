# Read-only guest timing probe: first runtime evidence for V9's failure

**Status:** diagnostic source/tool only; **not** a dynamic-FPS mod or a playable IPS.
The original fixed-30 and native adaptive mods remain on main. The V7/V8A/V9
IPS experiments remain unsuitable for gameplay.

## Why this experiment matters

V9 read a 64-bit field from the FPS-state object at offset +0x100,
**assumed without evidence** that it contained a per-render frame duration,
and clipped the calculated step to four ticks. The user's observation
(normal speed at roughly 15 FPS, speed-up above 15, slow-down below 15)
closely fits *permanent* four-tick saturation, but nobody has read
the value of that field while the game was actually running.

This [independently authored probe](guest_timer_probe.py) connects over the
emulator's local, opt-in AArch64 GDB remote stub, sets a temporary breakpoint
at the **unmodified original** frame-step division, and reads only:

- FPS state +0x100 (V9's **unverified** timer input);
- FPS state +0x148 and +0x150 (nearby candidate timing fields);
- FPS state +0x2C8 (**raw four-byte value**; was incorrectly called a float target FPS in the original probe). The updated probe also reads the live `s0`, `s1` and `s8` register bits at the division.

It takes at most 40 samples (default 12), removes the breakpoint and resumes
guest execution. Each output is just numeric fields plus a derived pattern
summary. There is no memory dump or game binary, no IPS, no runtime writing
except the debugger's temporary breakpoint. The script binds only to
127.0.0.1 and has no HTTP or upload functionality.

**Important:** Repeated debugger breakpoints pause execution and therefore
distort frame timing. These samples may identify whether +0x100 is
*cumulative*, unchanged, or immediately above the V9 saturation threshold;
**they cannot** prove the game's speed or provide unbiased real-time
frame durations. The candidate +0x148/+0x150 fields' **units and meaning are
not verified**, either. Do not use values from here as new patch constants.

## Requirements

- Emulator build containing a compatible GDB stub; Lichii exposes
  \`-d PORT\` / \`--debug PORT\` and has a Debugging/GDB option.
  See [the upstream Lichii launch options](https://github.com/zortos293/Lichii/blob/nx2/src/core/launch_params.cpp)
  and [GDB client tool](https://github.com/zortos293/Lichii/blob/nx2/tools/nx2/gdbrsp.py).
- A private legally obtained game. **No** NSO needs to be given to this
  script, and the script never opens game executables.
- Python 3.10+ on the emulator PC, standard library only.
- No other FPS mod, including built-in Orchid FPS patches, enabled.
- Back up saves before any emulator debugging session.
- Game build ID E0F3 or 33FA, with the corresponding exact installed game.
- Access to the **current-session** \`eden_log.txt\` (only read locally).

## Running it

1. Copy \`guest_timer_probe.py\` to your PC with the emulator.
2. Disable **all** FPS mods and frame generation; set emulator speed to 100%.
3. Launch the emulator with GDB debugging enabled on port 6543. One example,
   subject to fork command-line support:

   \`\`\`powershell
   .\lichii.exe --debug 6543
   \`\`\`

4. Load the game and start the diagnostic in a separate terminal, selecting
   the exact build ID:

   \`\`\`powershell
   py -3 .\guest_timer_probe.py --build-id E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348 --log "C:\path\to\user\log\eden_log.txt" --phase menu --samples 12 --output menu_timing.json
   \`\`\`

   For the base build use
   \`33FA6C2C23848282A77E8B88A0A93F4887C55920\`.
   The target log stays **on your PC** and is never copied.
   If the emulator has a different GDB port, supply \`--port 6543\`
   with its actual value. The game may be paused until the diagnostic attaches.
5. The script resumes emulation and waits for you to press **Enter**.
   Once the desired menu or gameplay scene is fully displayed, press Enter
   in the terminal. It momentarily interrupts the game, checks that
   the original instruction is present, samples a few frame-step calls,
   restores the breakpoint and resumes gameplay.
6. Restart the emulator if necessary and repeat with
   \`--phase gameplay --output gameplay_timing.json\`.
   If you previously left a debugger attached, close it first.

**If the emulator doesn't expose the GDB stub, this experiment cannot
run on that fork.** Do not modify the game's executable to force it.
Do not substitute a main base from a different game/update if the
opcode verification fails. A stale or incompatible guest module is
rejected before any breakpoint is armed.

The alternative \`--main-base 0x...\` accepts the current process
\`main\` load address reported in the emulator log, when a log file
cannot be located automatically. Never confuse module offsets
(\`main+0x006E6CC4\`) with its runtime virtual address.

## How to interpret output

A real per-render duration in **31.25 MHz counter ticks** would be
roughly 520,833 at 60 FPS, 1,041,667 at 30 FPS, and 2,083,333
at 15 FPS. These are useful *hypotheses only*. They are not evidence
that the game stores fields in those units.

- If \`field_100\` increases monotonically and is much larger than
  2,083,333, V9's four-tick clamp would be permanently saturated,
  **assuming** the original pointer chain matches the V9 patch.
- If \`field_100\` is constant or changes only at scene load, it is
  not a fresh per-present delta.
- If \`field_100\` is modest and tracks changes in observed frame
  pacing, we still must identify its **write instructions** and units
  before treating it as timing data.
- If the samples don't reach the breakpoint or the FPS-state memory is
  unreadable, document that. It might indicate this path does not execute
  in the scene, or the analysis of register state is incomplete.

The JSON output contains no executable bytes, keys, saves or raw
memory dumps, but **review it before sharing**, since unknown game
fields are intentionally sampled. Do not upload the private emulator
log itself to a public repository.

## Verification and limitations

The GDB packet framing, little-endian register decoding, opcode guard,
field sampler, and pattern report are covered by synthetic unit tests.
A separate fake-stub integration test verifies the full attach,
breakpoint/single-step, cleanup and resume command sequence without
running an emulator or proprietary code.

**The probe has NOT been tested against a live Lichii/Eglantine session.**
GDB stub behavior can differ by emulator version; when it does,
capture the diagnostic's error message but do not disable its
original-instruction safety checks.

This is a diagnostic milestone, not evidence of fully dynamic gameplay.
When runtime data validates an actual timer source and update cadence,
a new independent IPS can be built with conservative safeguards.

## Troubleshooting a mismatched original instruction

**2026-11-06 Linux Eglantine field report:** The tester enabled GDB on port
6543 and the diagnostic successfully connected and resumed the guest. After
pressing Enter to sample the menu it aborted at
`verify_unmodified_hook()` with "Timing hook is not original". The user's
previously uploaded Eglantine log showed the updated E0F3 build with
`main` at `0x80e26000`, **but that log ended with a full emulator shutdown**.
That base was copied into a subsequent debugging command. It may be stale.
This exception is **not evidence the user forgot to disable mods**.

The current script has a safe `--check-hook` option. After a fresh emulator
launch, while it is waiting for the debugger, run:

```sh
python3 guest_timer_probe.py \
  --build-id E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348 \
  --main-base 0x80e26000 --phase menu --check-hook
```

This reports the expected and observed **single 32-bit instruction**
and guest address, sets **no breakpoint**, and resumes the game.
Use the `0x80e26000` value only as a diagnostic for the earlier log,
not as the source of truth for future sessions. Prefer replacing
`--main-base` with `--log "/path/to/CURRENT/eden_log.txt"` so the
script extracts the **latest** `main` load address after the game loads.

If `original_hook_matches` is false, **do not override it**. Send the
JSON and a fresh current-session log; distinguish an old base, an
unexpected code mapping, a changed original revision, and a real patch.
If it is true, the user can retry the main 12-sample menu trace with
the same **current** launch base, but the emulator must be relaunched
between debugger sessions for predictable initial halt state.


## First real menu run and corrected field labels

The user successfully captured 12 menu samples with the original E0F3
hook and reported the JSON. The underlying `+0x2c8` bytes were
`0x0000003c` (integer 60), **not** floating-point 60.0. In addition,
breakpoint overhead inflated `+0x100` to approximately 0.82 seconds
in most samples. See [MENU_TIMING_FIRST_TRACE.md](MENU_TIMING_FIRST_TRACE.md).

**Download the updated probe before collecting gameplay data.** The
corrected JSON keys are `field_2c8_raw_u32`,
`field_2c8_float_interpretation` and, when GDB supplies vector
registers, `fdiv_denominator_s0`, `fdiv_numerator_s1` and
`fdiv_prior_s8`. The actual register operands have not yet been
measured in a live session; do not assume the x21 object field is the
FPS divisor.
