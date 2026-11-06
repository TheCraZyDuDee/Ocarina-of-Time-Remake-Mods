# Development and contributing

## How mods are organized

Each mod gets a short README in its own folder, grouped by purpose:

```text
mods/
  README.md                 # catalog of categories
  fps/
    README.md               # category overview and compatibility
    build.py                # FPS patch generator
    fixed-30/README.md
    native-adaptive/README.md
    variable-average/README.md
releases/                   # ready-to-install ZIP archives (unchanged paths)
tests/test_fps.py           # checks for the FPS patches and documentation
```

For **future non-FPS mods**, create a category such as `mods/graphics/` or `mods/gameplay/` and add a separate `<mod-name>/README.md`. Link each mod from its category page, [the catalog](../mods/README.md) and optionally the [project home](../README.md). Keep the description, supported build IDs, installation, and test status on the mod's page. Put any new build logic next to its category rather than expanding the FPS generator.

## Build and test

From the repository root (Python 3 standard library only):

```sh
python3 -m unittest discover -s tests -v
python3 mods/fps/build.py --output-dir dist
```

The generator creates deterministic IPS32 ZIPs for the two supported executable builds. The checks verify patch hashes, IPS32 formatting, ZIP layout, documentation links and byte-for-byte equality with the ZIPs committed under `releases/`.

## Optional local opcode verification

If you own a **decompressed** NSO matching the build ID, you can verify its segment digests and original opcode words without publishing it:

```sh
python3 mods/fps/build.py --mode fixed-30 --build-id E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348 --verify-nso /private/path/to/main.nso --output-dir dist
```

Verification reads the NSO but does **not** modify or include it in a ZIP. Patches for additional builds require independent research and original-byte validation.

## FPS patch notes

- **Fixed 30 FPS:** uses the instruction addresses and parameters described by [Orchid](https://github.com/MythosOfs/Orchid/blob/main/src/core/file_sys/patch_manager.cpp).
- **Native Adaptive:** bypasses the forced-mode early return to allow the game's native discrete frame intervals.
- **Variable-average (experimental):** injects small independently written ARM64 routines into verified zero-filled code space, alternating supported frame intervals. It may jitter and remains gameplay-untested.

IPS32 files contain a `IPS32` header, 4-byte big-endian file offsets, 2-byte big-endian lengths, replacement bytes, and an `EEOF` terminator. Module addresses are increased by the NSO header size `0x100`.

## Releases and clean contributions

Ready-to-install ZIPs stay under `releases/` to avoid breaking existing links. Pushing a version tag such as `v1.0.0` triggers the release workflow, which rebuilds all current mod ZIPs.

**Never commit** game executables, decrypted dumps, keys, extracted game art/audio, or personal logs. Submit small, independently written patch instructions and documentation only. See [attribution and license notes](ATTRIBUTION.md).
