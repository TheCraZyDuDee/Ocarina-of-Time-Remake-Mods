# True Dynamic FPS — E0F3

**Status:** First successful live user playtest. The tested E0F3 isolated-step V10 kept apparent gameplay speed normal while actual rendering varied around **10–15 and 30–45 FPS**. The precise speed of every physics and cutscene system has not been independently timed.

**[Download True Dynamic FPS](../../../releases/oot-true-dynamic-e0f3.zip)**

## Compatibility

- **Title ID:** `0400486024DEC000`
- **Only supported main build:** `E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348`
- **Unsupported:** `33FA6C2C23848282A77E8B88A0A93F4887C55920` (base) and other executable versions.

The mod scales the game's existing simulation step using a physical-counter time delta. Unlike failed combined V9, **it leaves the original frame-rate guard and presentation interval untouched**. It does not increase emulator speed, add frame generation, or work at zero rendered FPS.

## Install

1. Back up saves. Disable all other FPS patches, including emulator built-in FPS mods.
2. Import the ZIP in the emulator's mod manager, or extract its inner `0400486024DEC000/` folder into the emulator `load/` directory.
3. Set emulator speed to **100%**, disable frame generation, restart, and confirm the IPS applies to E0F3.
4. If you encounter unexpected cutscene, menu, loading, collision or animation timing, disable it and report the situation.

Do not combine it with Fixed 30, Native Adaptive, V9 or any older dynamic/variable-average experiments.

## Reproducibility and boundaries

The release contains **exactly the same 209-byte E0F3 IPS** that succeeded in the user's V10 gameplay test; only the ZIP folder/README labeling was cleaned up.

**IPS SHA-256:** `306e36cec3efc28a38df627ed38245fe29008855a85cfe4a249a7d8fb2fd1365`.

Step size is bounded to **0.5–4.0 nominal simulation units per update**. Very long stalls or sustained extreme FPS drops are not guaranteed to track wall-clock time perfectly. The positive test is practical gameplay evidence, not complete formal validation.

Rebuild with `python3 mods/fps/build.py --mode true-dynamic --output-dir dist`. No original NSO or external Python package is needed.

[All FPS mods](../README.md) · [Engineering handoff](../research/true-dynamic/HANDOFF.md) · [Project home](../../../README.md)
