# Fixed 30 FPS

**Status:** Normal-speed gameplay confirmed by a tester on build `E0F3CCFA...`. The second build is statically verified but not gameplay-tested.

Locks the game's **own frame-rate controller** to 30 FPS while using its native simulation timing. This is not a generic emulator speed limiter.

**[Download the standalone ZIP](../../../releases/oot-fixed-30-both-builds.zip)**

Supports both builds listed in the [FPS compatibility table](../README.md#compatibility).

## Install

Import the ZIP into a compatible emulator or extract its title-ID folder into the emulator's `load/` directory. Disable other FPS mods and Orchid's built-in FPS patch. Restart at 100% emulator speed.

Source and build logic: [`../build.py`](../build.py) (mode `fixed-30`). Fixed-FPS instruction locations were documented by [Orchid](https://github.com/MythosOfs/Orchid).

[All FPS mods](../README.md) · [Project home](../../../README.md)
