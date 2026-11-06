# Variable-average FPS

**Status: Experimental and not gameplay-tested.** The scheduling idea was mathematically checked, but actual gameplay, physics and frame pacing remain unverified.

Attempts intermediate **average** FPS values by alternating the game's supported 1/2/3-refresh-interval simulation steps. For example, mixing 2- and 3-interval frames may produce an average between 20 and 30 FPS.

This is **not** true continuously variable simulation timing. It can introduce uneven frame delivery, and performance is still limited by the emulator and hardware.

**[Download the experimental ZIP](../../../releases/oot-variable-both-builds.zip)**

Supports both builds listed in the [FPS compatibility table](../README.md#compatibility).

## Install and test

Import the ZIP into a compatible emulator or extract its title-ID folder into `load/`. Disable other FPS mods and Orchid's built-in FPS patch, back up saves, and restart at 100% emulator speed.

Test movement, jump distance, animations and frametime consistency before relying on this build.

Source and build logic: [`../build.py`](../build.py) (mode `variable`).

[All FPS mods](../README.md) · [Project home](../../../README.md)
