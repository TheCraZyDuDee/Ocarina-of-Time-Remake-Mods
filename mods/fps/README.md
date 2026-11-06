# Frame rate and performance

FPS mods are **separate alternatives**. Install and enable only one at a time.

| Mod | Behavior | Compatible main builds | Evidence |
| --- | --- | --- | --- |
| [True Dynamic FPS](true-dynamic/README.md) | Uses measured elapsed time to scale simulation without forcing a new presentation interval. | **E0F3 only** | User reports normal gameplay speed at approximately 10–15 and 30–45 actual FPS. |
| [Fixed 30 FPS](fixed-30/README.md) | Native game 30 FPS lock. | E0F3 + 33FA | Normal speed confirmed on E0F3. |
| [Native Adaptive FPS](native-adaptive/README.md) | Native discrete 20/30/60 modes. | E0F3 + 33FA | 20 FPS gameplay reported good; other conditions less tested. |

## Compatibility

Title ID: `0400486024DEC000`.

- **E0F3 update:** `E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348`.
- **33FA base:** `33FA6C2C23848282A77E8B88A0A93F4887C55920`.

**True Dynamic FPS is E0F3 only.** Unlike the two existing native alternatives, it has no IPS for 33FA. The older untested Variable-average experiment was retired.

## Installation

1. Read the selected mod's README and download its ZIP.
2. Import via the emulator mod manager or extract the inner title-ID folder into `load/`.
3. Disable all other FPS mods and Orchid's built-in FPS patch. Set emulator speed to **100%**, disable frame generation, back up saves, then restart.
4. Verify the IPS was applied and the emulator loaded the supported executable.

The dynamic mod's success is a **user-reported gameplay test**, not a stopwatch study of every scene. The bounded step may not sustain perfect game time during extended stalls or very low FPS.

## Build and tests

```sh
python3 mods/fps/build.py --output-dir dist
python3 -m unittest discover -s tests -v
```

The generator pins the exact E0F3 IPS SHA-256 from the tested V10 and regenerates every release ZIP byte-for-byte.

[Research handoff](research/true-dynamic/HANDOFF.md) · [Development](../../docs/DEVELOPMENT.md) · [Catalog](../README.md)
