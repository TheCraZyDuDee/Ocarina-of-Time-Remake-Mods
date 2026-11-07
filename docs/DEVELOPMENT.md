# Building and contributing

You'll need Python 3. The build and tests use only the standard library and don't need a game executable.

Run these commands from the repository root:

```sh
python3 mods/fps/build.py --output-dir dist
python3 -m unittest discover -s tests -v
```

## Repository layout

| Path | Contents |
| --- | --- |
| `mods/<category>/<mod>/` | Each mod's README and any files specific to it |
| `mods/fps/build.py` | Shared generator for the three FPS mods |
| `releases/` | Downloadable ZIPs, kept here so download URLs stay stable |
| `tests/` | Patch and release checks |
| `docs/fps/` | FPS implementation notes |
| `docs/ai/` | AI-assisted research history and handoff notes |
| `.github/workflows/` | Verification and release publishing |

## FPS builds

| Mode | Output ZIP | Supported builds |
| --- | --- | --- |
| `fixed-30` | `oot-fixed-30-both-builds.zip` | E0F3, 33FA |
| `adaptive` | `oot-adaptive-both-builds.zip` | E0F3, 33FA |
| `true-dynamic` | `oot-true-dynamic-e0f3.zip` | E0F3 only |

To build just one mod, add `--mode`, for example:

```sh
python3 mods/fps/build.py --mode fixed-30 --output-dir dist
```

ZIPs use deterministic metadata. Tests and CI compare rebuilt archives byte for byte with `releases/`. If you intentionally change an archive's contents, rebuild it into `releases/` and include the updated ZIP in the same change.

The tested True Dynamic patch is pinned by SHA-256. See its [technical notes](fps/true-dynamic.md) before changing it.

## Optional ARM64 execution audit

The True Dynamic helper can also be executed in a synthetic ARM64 environment:

```sh
python3 -m pip install unicorn==2.1.4
python3 tools/audit_dynamic.py -v
```

This developer check is separate from the standard-library build and release tests. See the [review notes](fps/true-dynamic-review.md) for its scope and results.

## Adding a mod

1. Create a folder under `mods/<category>/<mod-name>/`. Reuse a category when it fits; add one for a different kind of mod.
2. Give it a README covering what it changes, supported builds, download, installation and known issues. Put shared instructions in the category README.
3. Keep mod-specific source with the mod. Share a generator within a category when mods use the same patching logic, as the FPS mods do.
4. Add a downloadable ZIP to `releases/` and link the mod from the root README and mod catalog. Update the category index too.
5. Add suitable build checks and document what was actually playtested. Addresses from one executable build mustn't be assumed to work on another.

Work on a branch and run the relevant tests before opening a pull request. Keep research and AI handoffs out of installation instructions; put them under `docs/` instead.

## Publishing

The `v*` tag workflow builds the FPS ZIPs and uploads them to a GitHub prerelease. Regular downloads remain in `releases/`.

Don't commit game executables, decrypted NSOs, keys, saves, extracted assets or private debugger logs. See [credits and distribution notes](ATTRIBUTION.md).
