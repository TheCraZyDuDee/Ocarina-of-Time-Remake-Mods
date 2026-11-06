# Ocarina of Time Remake Mods

Standalone **IPS32 / ExeFS patches** for *The Legend of Zelda: Ocarina of Time* on Nintendo Switch 2. Developed with AI assistance.

## Mods and downloads

| Mod | Description | Status |
| --- | --- | --- |
| [Fixed 30 FPS](releases/oot-fixed-30-both-builds.zip) | Uses the game's native 30 FPS controller; no slow motion. | **Gameplay-tested** on the E0F3 build. |
| [Adaptive FPS](releases/oot-adaptive-both-builds.zip) | Enables the game's native adaptive **20 / 30 / 60 FPS** modes. | **20 FPS observed working**; other modes need testing. |
| [Variable-average FPS](releases/oot-variable-both-builds.zip) | Attempts intermediate *average* rates by mixing supported frame intervals. | **Experimental and untested**; possible uneven pacing. |

Each ZIP supports **both** documented executable versions; the emulator loads the matching IPS by build ID.

**Supported game Title ID:** `0400486024DEC000`

- `E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348` — update v131072 in Orchid's notes (user-tested fixed 30 FPS).
- `33FA6C2C23848282A77E8B88A0A93F4887C55920` — base v65536 in Orchid's notes (statically checked).

These version labels are from [Orchid's source](https://github.com/MythosOfs/Orchid/blob/main/src/core/file_sys/patch_manager.cpp); verify the **loaded build ID** in your emulator log.

## Install

1. Download **one ZIP** from the table above.
2. Import it with a compatible emulator mod manager, or extract its `0400486024DEC000/` folder into the emulator's `load/` directory.
3. **Enable only one FPS mod at a time.** Disable earlier FPS patches and Orchid's built-in 30 FPS patch.
4. Fully restart the game at **100% emulation speed** with frame generation turned off.
5. If nothing changes, look for `Applying IPS patch from mod` in the emulator's log and check the loaded build ID.

Back up saves before using experimental mods. A reported FPS number does not by itself prove that physics and gameplay speed are correct.

## Build from source

Source: [`src/build.py`](src/build.py); regression tests: [`tests/test_build.py`](tests/test_build.py).

```sh
python3 src/build.py --output-dir dist
python3 -m unittest discover -s tests -v
```

The builder requires **only Python 3's standard library**. No Nintendo data or other external dependencies are downloaded. Optional local verification against your own *decompressed* game executable is described in [Development](docs/DEVELOPMENT.md).

The installable archives are in [`releases/`](releases/). The automated checks run on commits, and version tags can be used to publish GitHub Releases.

## License and credits

This repository's original source, documentation, and small compatibility patches are under the [MIT license](LICENSE). No game binaries, keys, game assets or copied emulator source are distributed. The fixed-FPS instruction locations were described by the [GPL-licensed Orchid emulator](https://github.com/MythosOfs/Orchid); no Orchid source files have been copied here. See [Attribution](docs/ATTRIBUTION.md).

Unofficial project. Not affiliated with or endorsed by Nintendo or emulator developers.
