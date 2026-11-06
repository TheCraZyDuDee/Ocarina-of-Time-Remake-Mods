# Experimental GDB write-site identification, not a playable mod

**Only proceed if the tester is comfortable with another debugger run.**
We already have a usable gameplay trace showing `s0 = s1 = 60.0`.
The remaining unknown is *who writes* the suspected duration at
`frame_state + 0x100`. Use the source-only diagnostic, not another IPS.

The helper [`guest_timer_write_trace.py`](guest_timer_write_trace.py)
imports the adjacent [`guest_timer_probe.py`](guest_timer_probe.py);
**both files must be in the same folder**, e.g.
`/home/l/Schreibtisch/Neuer Ordner/`. Python standard library only.

On the user's CachyOS Linux, in a terminal, download both files:

```bash
cd "/home/l/Schreibtisch/Neuer Ordner"
curl -fL 'https://raw.githubusercontent.com/TheCraZyDuDee/Ocarina-of-Time-Remake-Mods/research/true-dynamic-fps/mods/fps/research/true-dynamic/guest_timer_probe.py' -o guest_timer_probe.py
curl -fL 'https://raw.githubusercontent.com/TheCraZyDuDee/Ocarina-of-Time-Remake-Mods/research/true-dynamic-fps/mods/fps/research/true-dynamic/guest_timer_write_trace.py' -o guest_timer_write_trace.py
```

Close and reopen Eglantine. Keep GDB Stub **enabled** on port 6543,
regular speed 100%, all installed FPS IPS mods **disabled**, and
back up saves before debugger sessions. Start the game; it may pause
until the debugger attaches. In another terminal, use:

```bash
cd "/home/l/Schreibtisch/Neuer Ordner"
python3 guest_timer_write_trace.py \
    --build-id E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348 \
    --log '/mnt/EmuStuff/Emulatoren/Switch 2/user/log/eden_log.txt' \
    --phase gameplay --offset 0x100 --hits 4 \
    --output gameplay_timer_write_locations.json
```

**Use the actual current-session `eden_log.txt` path that worked in
prior tests**, if it differs from the example path. Do not reuse a
hard-coded `--main-base` from a previous Eglantine launch.

After the script connects, let the game reach gameplay, then press Enter
in the terminal. It temporarily breaks at the *original unpatched*
`fdiv` instruction, reads the current state pointer from `x21`, removes
the code breakpoint, then watches **one eight-byte field** for four
writes. The debugger pauses for each hit, captures only the instruction
location and numeric field value, and resumes the game. It may take a
few seconds and will not measure accurate FPS.

If successful, upload only **`gameplay_timer_write_locations.json`**.
If Eglantine refuses the watchpoint (`Z2`), times out, freezes, or reports
an original-instruction mismatch, send the *error message* and leave the
old, stable mods alone. We can adjust the diagnostic without repeatedly
interrupting the game.

This script is **synthetic-tested but not live-verified** on your exact
Eglantine build; no guarantee it works. It sets a temporary 4-byte
software breakpoint to discover `x21`, plus an 8-byte debugger watchpoint
(`Z2`) for up to four writes. It does **not** install FPS mods or alter
saves. Unknown-game-address and error paths fail closed.

The purpose is **instruction provenance**, not frame timing: because
watchpoints stop the guest, observed time values will be inflated and
cannot validate V9's units or real-time gameplay speed.
## Results from the first real run

The tester observed 4 writes to +0x100, all reporting the exact E0F3
code location main+0x0346C7EC. Values were 7,040,467; 19,138,755;
476,073; and 1,263,539, in that order. No need to repeat watchpoint
sampling yet. Instead capture a private small instruction window around
the write PC using guest_writer_static_window.py, so that the exact writer
and its inputs can be identified. See TIMER_WRITER_FIRST_TRACE.md.
