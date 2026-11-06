# Future E0F3 callback-target check (opt-in, no action required yet)

The 2026-11-06 source audit established that the original E0F3
timing-configuration converter at `main+0x03B4E300` stores a rounded
nominal rate and, **when its optional `config+0x1C8` pointer is set**,
invokes a virtual method at the object's vtable offset `+0x10`.

We do not yet know whether the pointer is populated in gameplay or
whether the callback changes presentation pacing, rate settings,
simulation state, or anything else. The original controller's
`LDR W1,[X20,#0x48]` was changed to `MOV W1,#1` by failed V9;
this independent patch complicates causal diagnosis. See
[V9_CAUSAL_INTERACTION_AUDIT.md](V9_CAUSAL_INTERACTION_AUDIT.md).

## Prepared diagnostic

The research branch now includes
[`guest_config_callback_resolver.py`](guest_config_callback_resolver.py)
and executable-free synthetic tests
`tests/test_guest_config_callback_resolver.py`.

The tool checks the original E0F3 frame-step opcode and seven callback
instructions before following the known live timing-config global
pointer chain (previously checked in the successful
`guest_frame_step_cadence_probe.py` run). It **reads**, but does not
invoke, the callback pointer, vtable pointer and method pointer.
If the method lies within the original E0F3 main TEXT range, it
collects only **128 bytes** of the target's code; if outside, it does
not blindly read executable bytes from an unknown module.
It installs no breakpoints, modifies no game memory, and resumes the
guest after the brief numeric/code capture.

It passed synthetic GitHub tests but has **not** been tested live on
Eglantine. Keep any produced JSON private: it might contain original
Nintendo code and guest memory addresses. Never commit or publish it.

## Procedure — only when new live evidence is requested

Keep `guest_timer_probe.py` in the same directory as the downloaded
`guest_config_callback_resolver.py`. Restart Eglantine with GDB
enabled on port 6543 and all FPS mods disabled. Start the game at its
**initial debugger stop**.

```sh
python3 guest_config_callback_resolver.py \
  --log '/mnt/EmuStuff/Emulatoren/Switch 2/user/log/eden_log.txt' \
  --output config_callback_target.json
```

Use the current real log path, not an old run's log.
The script resumes the game; load a stable gameplay scene and press
Enter in the terminal. It briefly interrupts the guest to inspect
the callback and then attempts to resume it. If any original opcode
or pointer validation fails, do **not** bypass the check; share the
error instead. Do not run a second debugger client concurrently.

There is **no reason to repeat the previous eight-hit callsite trace**.
Before testing or distributing V10, the critical remaining gap is
the optional callback's behavior and the three-way guard/presentation/
simulation-step interaction in archived V9.
