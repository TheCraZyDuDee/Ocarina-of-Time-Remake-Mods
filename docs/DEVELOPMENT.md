# Development

## Layout

- `src/build.py` — patch addresses, ARM64 replacement words, IPS32/ZIP builder, optional dump checks.
- `tests/` — patch regression hashes, IPS32 parsing, ZIP/filename checks; no game data required.
- `releases/` — installable ZIPs, each containing two build-ID-specific IPS32 files.
- `.github/workflows/` — automated validation and tag-based GitHub Releases.

Build and test from the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 src/build.py --output-dir dist
```

The generator uses only Python's standard library and produces deterministic ZIPs. The patch bytes match the verified versions originally built from the two executable revisions. ZIPs contain **only changed instructions, patch metadata and a small README**.

## Optional local opcode checks

If you own a **decompressed** NSO dump with the correct build ID, you can verify its segment digests and original instruction words before patching, without committing or uploading it:

```sh
python3 src/build.py --mode fixed-30 --build-id E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348 --verify-nso /private/path/to/main.nso --output-dir dist
```

The verification command reads the NSO and checks its ID, three segment SHA-256 digests and exact original opcode values. It does **not** modify the file or package it in the ZIP. Different builds require new research and independent opcode verification.

## Design notes

IPS32 uses `IPS32` as its magic, a four-byte big-endian file offset, two-byte big-endian record length, the replacement bytes and an `EEOF` terminator. Offsets in these patches are module-relative plus the NSO header size `0x100`.

- **Fixed:** uses Orchid's published *Ocarina* frame-controller patch locations and replacement instruction parameters.
- **Adaptive:** bypasses a manual/forced-mode early return so the game's discrete controller can run; not guaranteed to perform well everywhere.
- **Variable-average (experimental):** injects short original ARM64 routines into previously zero-filled code padding and alternates native frame intervals. Its *average* may vary between 20–60 FPS, but individual intervals remain 1/2/3 vblanks. This can introduce irregular frame pacing and needs user testing.

A standalone game patch cannot accelerate an emulator that is CPU/GPU-bound, nor guarantee normal speed below the engine's minimum supported simulation frame rate.

## Publishing a GitHub Release

Push a version tag such as `v1.0.0` to this repository. The GitHub Actions `publish.yml` workflow tests and rebuilds the three ZIPs, then creates/updates a release with those assets. Mark versions that include untested changes as prereleases when appropriate.

Do not publish decrypted executables, NSOs, NSP/XCI/NCA files, keys, screenshots/assets extracted from the game or private debug logs. Use only independently created patch instructions and documentation.