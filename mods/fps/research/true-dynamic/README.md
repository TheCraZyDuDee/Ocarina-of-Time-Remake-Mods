# True dynamic FPS — research workspace

**Status: research only; no installable mod or release in this folder.**

Goal: keep *Ocarina of Time* simulation at normal real-time speed while rendered FPS changes, without assuming presentation rate is 20, 30 or 60. The two supported executable revisions must both remain supported.

This is separate from the [working FPS mods](../../README.md). **Do not replace them with any of the failed experiments.**

## What we learned from testing

| Experiment | Observed result | Lesson |
| --- | --- | --- |
| Fixed 30 FPS (v5) | Normal gameplay speed | Native game time-step and presentation interval agree. |
| Native adaptive (v6 predecessor) | 20 FPS played normally | Native discrete intervals can work. |
| 15 FPS probe | Seemed normal at 15 FPS | 4 ticks/frame can work when presented at 15 FPS. |
| 10 and 5 FPS probes | Still presented ~15 FPS, physics/animations too fast | 6 or 12 ticks/frame while presenting at 15 FPS means ~1.5x or ~3x speed. |
| Measured-time v7 | Menu loaded; entering gameplay produced black screen / 0 FPS | Injected timing hook is unsafe; exact cause unconfirmed. |
| Uncapped presentation v8A | Menus and gameplay present, but animation/physics fast at high FPS | Presentation must not be uncoupled from simulation without replacing its time-base. |

The source-derived fixed patch initializes the interval and sets the game's target frame rate to `60 / interval`. V8A forced the **presentation** argument to 1 but left the **simulation** target derived from a different interval. Thus two simulation ticks per rendered frame at 60 FPS would run ~2x speed. This matches the user report.

## Mario Kart World reference

[Lichii's MKW dynamic FPS](https://github.com/zortos293/Lichii/blob/main/src/core/loader/nso.cpp) takes a **game-specific** approach:
1. It selects MKW's built-in dynamic mode instead of its 30 FPS mode.
2. It redirects MKW's timing input from a partial frame-duration field to a whole-frame-duration field.
3. The [emulator's present pacer](https://github.com/zortos293/Lichii/blob/main/src/core/hle/service/nx2_gsv.h) uses interval 1 for that verified MKW dynamic mode.

This is useful *architecture*, **not a patch that can be copied into Ocarina**. The two games have different controllers, time managers and object layouts. In particular, forcing OoT's presentation interval to 1 without correcting its simulation produced fast gameplay (v8A).

## Source and checks

- [`timing_model.py`](timing_model.py) — independently written **fixed-60-Hz update-loop model**, preserving fractional elapsed time and explicitly reporting when low FPS exceeds a substep budget. It does not modify or emulate the game.
- [`inspect_controller.py`](inspect_controller.py) — **read-only** original-code checks for each build; requires your own local *decompressed* NSO. It prints opcode matches and checksum status, never copies files or generates IPS patches.
- [Research regression tests](../../../../tests/test_true_dynamic_research.py) — known failure ratios, frame-rate transitions, fractional carry, and low-FPS limitations.

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
python3 mods/fps/research/true-dynamic/inspect_controller.py /path/to/your/decompressed/main.nso
```

Never commit dumps, keys, game assets or local emulator logs.

## New: two timing controllers and shared rate validator

[Two-controller research and code map](TWO_CONTROLLERS.md) identifies a separate
FPS-target controller in both executable versions. It calls the **same** frame
rate setter used by the native interval-based controller. The shared setter
generally rejects targets that do not divide 60 Hz; a guarded 40+ FPS path
may be relevant but has not been verified in gameplay.

New read-only tools:
- [`map_time_managers.py`](map_time_managers.py) — checks original opcode
  fingerprints and three direct calls in both builds, without modifying game data.
- [`frame_rate_acceptance.py`](frame_rate_acceptance.py) — models the
  general-path FPS rejection/suggestion and guarded 40+ FPS validation.
- [Regression tests](../../../../tests/test_time_manager_map.py) — executable-free
  tests for branch decoding and rate acceptance.

Static evidence does **not** show which controller runs during menus versus
gameplay. A safe hook into the actual simulation dispatcher is still required.

## Remaining work before another IPS

1. Locate and verify **the actual per-frame simulation dispatcher**, rather than inferring simulation time from the present callback alone.
2. Establish whether the game's frame time readings include vsync waits, GPU stalls, loading transitions and menu time. The MKW whole-frame-time trick is a possible *lead*, not established for OoT.
3. Determine whether the game can execute multiple **fixed** 1/60-second updates per rendered frame; simply multiplying a physics delta has already broken jumps.
4. Make the frame-time accumulator reset only at a verified lifecycle boundary, and cap/handle loading spikes without entering a catch-up loop.
5. Verify preservation of register state, branch paths, code-cave lifetime and both executable builds before producing an **outside-repository** experimental ZIP.
6. Test menus, save loading, timers, jumps and scene transitions at variable actual FPS, not only the FPS overlay.

**At 0 displayed FPS, a render-driven loop cannot advance.** Maintaining simulation when rendering stops requires a separate running update thread. Under severe emulator overload, even decoupled updates can fall behind.

No generated patch, proprietary game data or GPL emulator code is included here. The source is original under this repository's MIT license.
