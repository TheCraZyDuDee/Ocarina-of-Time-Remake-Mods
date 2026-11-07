# FPS mods

Choose one FPS mod. They change the same timing systems and shouldn't be combined.

| Mod | What to expect | Supported builds | Testing so far |
| --- | --- | --- | --- |
| [True Dynamic FPS](true-dynamic/README.md) | Adjusts simulation timing as the frame rate changes. | E0F3 only | A tester reported normal-looking speed at about 10–15 and 30–45 FPS. |
| [Fixed 30 FPS](fixed-30/README.md) | Locks the game's own frame-rate controller to 30 FPS. | E0F3, 33FA | Normal speed confirmed on E0F3; 33FA hasn't been playtested. |
| [Native Adaptive FPS](native-adaptive/README.md) | Switches between the game's 20, 30 and 60 FPS modes. | E0F3, 33FA | Good behavior reported at 20 FPS; 30 and 60 haven't been independently confirmed. |

## Compatibility

The game title ID is `0400486024DEC000`. Check the executable build ID in your emulator's game information or log; the title ID alone isn't enough.

| Build | Full executable build ID |
| --- | --- |
| E0F3 (update) | `E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348` |
| 33FA (base) | `33FA6C2C23848282A77E8B88A0A93F4887C55920` |

True Dynamic FPS supports **E0F3 only**. Other executable builds aren't supported by these downloads.

## Installation

1. Back up your saves and download the ZIP from your chosen mod's page.
2. Import the ZIP using your emulator's mod manager. For manual installation, extract it and copy the `0400486024DEC000/` folder into the emulator's `load/` directory.
3. Enable only your chosen FPS mod. Disable other FPS patches, including Orchid's built-in FPS patch.
4. Set emulator speed to **100%**, turn off frame generation, and restart the game.
5. Check the emulator log to confirm the IPS patch applied to the expected build.

For manual installs, the patch should end up at `load/0400486024DEC000/<mod name>/exefs/<build ID>.ips`.

To uninstall, disable the mod in your emulator or remove its folder from `load/0400486024DEC000/`, then restart.

If timing, movement or cutscenes behave oddly, disable the mod and report your build ID, emulator version, chosen mod and where it happened in a [GitHub issue](https://github.com/TheCraZyDuDee/Ocarina-of-Time-Remake-Mods/issues). Please don't attach game files or keys.

[All mods](../README.md) · [Project home](../../README.md)
