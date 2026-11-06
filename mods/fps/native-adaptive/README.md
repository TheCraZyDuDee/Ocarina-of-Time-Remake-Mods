# Native Adaptive FPS

**Status:** Experimental. A tester reported good gameplay behavior at **20 FPS**; the 30 and 60 FPS modes have not been independently confirmed.

Allows the game's existing adaptive frame controller to select between **20, 30 and 60 FPS** (1, 2 or 3 refresh intervals at 60 Hz). These are native discrete steps, **not** fully arbitrary FPS values.

**[Download the standalone ZIP](../../../releases/oot-adaptive-both-builds.zip)**

Supports both builds listed in the [FPS compatibility table](../README.md#compatibility).

## Install

Import the ZIP into a compatible emulator or extract its title-ID folder into the emulator's `load/` directory. Disable other FPS mods and Orchid's built-in FPS patch. Restart at 100% emulator speed.

Source and build logic: [`../build.py`](../build.py) (mode `adaptive`). Test animations, movement and frame pacing if your system can reach multiple FPS modes.

[All FPS mods](../README.md) · [Project home](../../../README.md)
