# Development and releases

The normal FPS mod workflow is now **one build command and one test command**, using only standard Python:

```sh
python3 mods/fps/build.py --output-dir dist
python3 -m unittest discover -s tests -v
```

`mods/fps/build.py` is the sole active generator. It produces:

| Mode | ZIP in `releases/` | Main build IDs |
| --- | --- | --- |
| `fixed-30` | `oot-fixed-30-both-builds.zip` | E0F3 + 33FA |
| `adaptive` | `oot-adaptive-both-builds.zip` | E0F3 + 33FA |
| `true-dynamic` | `oot-true-dynamic-e0f3.zip` | **E0F3 only** |

The generator checks all IPS32 hashes, uses deterministic ZIP metadata, and needs no Nintendo NSO. CI regenerates the archives and compares them byte-for-byte with the committed ZIPs. The E0F3 True Dynamic IPS must retain the user-tested SHA-256 `306e36cec3efc28a38df627ed38245fe29008855a85cfe4a249a7d8fb2fd1365` until a replacement is independently tested.

## Maintaining or adding a mod

1. Use a separate branch; identify the **exact executable build**. Never assume 33FA and E0F3 offsets are interchangeable.
2. Modify the independent IPS replacements and the relevant mod README. Do not modify the tested True Dynamic helper without demonstrated need.
3. Rebuild ZIPs and run tests. Confirm the PR's GitHub Actions check passes.
4. Merge only verified changes. Normal releases are in `releases/`; the optional `v*` tag workflow publishes GitHub Release attachments.

The retired untested Variable-average mode was removed from the current tree. Detailed E0F3 research and legacy debugger scripts remain recoverable from the [historical research snapshot](../mods/fps/research/true-dynamic/HANDOFF.md), not on the default build/test path.

**Do not commit Nintendo executables, decrypted NSOs, original code windows, keys, saves, extracted game assets or private logs.** IPS payloads contain independently authored replacement instructions. See [attribution](ATTRIBUTION.md).
