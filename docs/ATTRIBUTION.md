# Attribution and distribution notes

- **Original project material:** the standalone IPS32 generator, experimental adaptive/variable patching approach, tests and documentation in this repository are distributed under its MIT license.
- **Orchid:** [MythosOfs/Orchid](https://github.com/MythosOfs/Orchid), `src/core/file_sys/patch_manager.cpp`, documents Ocarina-specific fixed-30 patch addresses, build IDs and instruction parameters. Its source is GPL-licensed. This repository credits the research but **does not copy Orchid's source code** or include an emulator build.
- **Lichii:** [zortos293/Lichii](https://github.com/zortos293/Lichii) was consulted for background on NSO loading, IPS32 support and emulator timing. No Lichii source is included here.
- **Nintendo:** the mods are small byte patches only. No game executable, decrypted NSO, encryption keys, game models, textures, audio, ROM or proprietary assets are distributed. You need your own legitimately obtained game data and compatible emulator software.

The MIT license applies only to the material this repository's contributors have the right to license. It does not override third-party licenses or grant rights to the underlying game. Small instruction parameters and addresses are provided as compatibility information; this is **not a legal opinion** about every jurisdiction or platform policy.

Do not submit proprietary dumps in issues, pull requests, release assets or git history. When contributing patches, provide build-ID-specific addresses and original/replacement words; test locally and submit the minimal patch generator changes.