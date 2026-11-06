# Controller investigation notes

These are **research observations**, not proof of a usable dynamic patch.

## Why the last experiments failed

- The renderer's requested swap interval can be clamped to **1–4** in [Lichii's NX2 presentation service](https://github.com/zortos293/Lichii/blob/main/src/core/hle/service/nx2_gsv.h). At 60 Hz, 4 vblanks is 15 FPS when the renderer is otherwise fast enough. This explains the 10/5 FPS probes still rendering ~15 FPS.
- The probes set the game's simulation interval to 6 and 12 ticks per frame. `render_fps * ticks_per_frame / 60` predicts 150% and 300% speed at 15 FPS, matching the user's fast-physics report.
- V8A replaced the present interval argument with 1, but the game separately calculates its frame-rate target as `60 / controller_interval`. Rendering at 60 while the time manager expects 30 is sufficient to explain doubled speed. It is not just a lack of GPU performance.
- V7 injected an accumulator that wrote into an existing controller field and changed multiple branches. It black-screened after a save loaded; the root cause is **unknown**. Do not reuse it or claim it was definitely an out-of-range simulation step.

## Known original code locations

Only short *original instruction words* and addresses are tracked by [the read-only inspector](inspect_controller.py), not executable code. Both builds' controller entry points differ by `0x5D670` in this region.

The controller reads CPU/GPU timing samples, selects an integer interval, derives a target rate of `60 / interval`, updates the game time manager, and forwards the selected interval to the present service. It is **not** established that these timing samples equal actual wall-clock duration across all loading and rendering paths.

The current v8A observation demonstrates that the **presentation and game time manager cannot be safely modified independently** without a verified elapsed-time path.

## Eglantine/Lichii Mario Kart World comparison

[Loader implementation](https://github.com/zortos293/Lichii/blob/main/src/core/loader/nso.cpp):
- MKW's frame controller reads a mode field from its own frame controller. Lichii selects the game's dynamic mode.
- In that specific mode it changes a load from one frame-time field to MKW's measured *whole frame time*. This is a two-part game-specific timing patch.
- The [present service](https://github.com/zortos293/Lichii/blob/main/src/core/hle/service/nx2_gsv.h) then enforces interval 1 for MKW only when the dynamic patch is confirmed to be loaded.

MKW's published testing reports normal speed at intermediate FPS on specific hardware, but occasional jitter/bugs remain. [Eglantine fork release notes](https://github.com/ZendNevs/Eglantine-ZendNevs/releases) explicitly warn about game-specific testing and time-step jitter. This does **not** establish that the same offsets or algorithm work in OoT.

## Acceptance criteria for a future experiment

- No black screen or infinite loading on any test save.
- Menus at normal speed, irrespective of presented FPS.
- Movement, jump distance, timers and animations remain tied to elapsed time.
- 30 to 60 FPS transitions do not accelerate the game; drops to 15 FPS do not halve it.
- An uninterrupted 10-second real-time test agrees with a comparable game timer (where that timer is expected to follow wall time).
- The mod is fail-closed for unknown build IDs and passes static patch-byte and register-preservation validation.

For now, **keep all builds and speculative IPS files out of this repository branch**.
