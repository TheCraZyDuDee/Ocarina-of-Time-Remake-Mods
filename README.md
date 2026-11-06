# Ocarina of Time Remake Mods

Standalone IPS32 mods for *The Legend of Zelda: Ocarina of Time* on Nintendo Switch 2, developed with AI assistance. Archives contain patches, **not Nintendo game files**.

## Download FPS mods

| Mod | Purpose | Build support | ZIP |
| --- | --- | --- | --- |
| [True Dynamic FPS](mods/fps/true-dynamic/README.md) | User reports normal gameplay speed at roughly 10–45 actual FPS. | **E0F3 only** | [Download](releases/oot-true-dynamic-e0f3.zip) |
| [Fixed 30 FPS](mods/fps/fixed-30/README.md) | Native fixed 30 FPS with normal game speed. | E0F3 and 33FA | [Download](releases/oot-fixed-30-both-builds.zip) |
| [Native Adaptive FPS](mods/fps/native-adaptive/README.md) | Native discrete 20/30/60 modes, not continuously variable. | E0F3 and 33FA | [Download](releases/oot-adaptive-both-builds.zip) |

The older untested *Variable-average FPS* ZIP has been retired. [Full mod catalog](mods/README.md) · [Compatibility](mods/fps/README.md)

## Installation

1. Download **one** FPS mod ZIP. Import it using a compatible emulator's mod manager, or extract the inner `0400486024DEC000/` folder into the emulator's `load/` directory.
2. Disable every other FPS patch (including emulator-provided FPS patches); use emulator speed **100%**, turn off frame generation and back up saves.
3. Restart the game and check that the executable build ID matches the chosen mod.

The True Dynamic release is **E0F3-only**. The 33FA build has not yet been validated for continuously variable simulation timing.

## Development

All published ZIPs build using Python's standard library:

```sh
python3 mods/fps/build.py --output-dir dist
python3 -m unittest discover -s tests -v
```

[Development guide](docs/DEVELOPMENT.md) · [Technical handoff](mods/fps/research/true-dynamic/HANDOFF.md) · [Attribution](docs/ATTRIBUTION.md) · [MIT License](LICENSE)

Unofficial mods, not endorsed by Nintendo. No proprietary executables, keys, saves, or extracted assets are included.
