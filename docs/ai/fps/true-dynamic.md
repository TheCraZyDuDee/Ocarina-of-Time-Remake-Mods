# True Dynamic FPS: AI research handoff

**Updated: 2026-11-07. Latest result: successful real user E0F3 V10 gameplay test.** The tester reports apparently normal game speed at approximately **10–15 FPS and 30–45 FPS** under Eglantine. This supersedes the failed V9 combined timing experiment; it is a qualitative playtest, not precise whole-game time/physics verification. Base **33FA remains unsupported**.

**Active source:** [`mods/fps/build.py`](../../../mods/fps/build.py) (`--mode true-dynamic`). **Download:** [E0F3 ZIP](../../../releases/oot-true-dynamic-e0f3.zip). These are the only commands for routine maintenance:

```sh
python3 mods/fps/build.py --output-dir dist
python3 -m unittest discover -s tests -v
```

## Verified design

- The original unmodified E0F3 game slows below actual 60 FPS.
- Original simulation step is `FDIV S8,S1,S0` at `main+0x006E6CC4`. V10 patches **only that hook and 19 independently authored helper/trampoline instructions in source-verified padding**.
- The 16-word helper reads physical-counter frame delta from the game's timing state at `+0x100`, scales by the current nominal frequency and `CNTFRQ_EL0`, and clamps to **0.5–4.0** step units.
- Helper control flow: `0x006E6CC4 → 0x006E1864 → 0x006E0F04 → 0x006F1804 → 0x006E6CC8`.
- **Controller guard `main+0x03B4EF90` and presentation load `main+0x03B4F080` are untouched.** V9 also modified those two sites and ran too fast. Static original-controller inspection found that forcing the presentation interval could conflict with its derived FPS rate. The V10 playtest supports removing the extra edits, but does not identify which single one caused V9's failure.
- Original E0F3 timing callback at `main+0x02F52DF0` consumes the variable step for some object countdown and interpolation work. Whole-engine correctness remains a separate concern.

**Golden IPS SHA-256:** `306e36cec3efc28a38df627ed38245fe29008855a85cfe4a249a7d8fb2fd1365` (**209 bytes, 20 records**). Original test ZIP SHA-256: `82489acb9aeb8876d69a898c4f2d4adc9b3f36ddc059f1c5cd50a264653d8b9c`. The new public ZIP only relabels/repackages the exact tested IPS; the instructions are byte-for-byte unchanged.

## Compatibility and outstanding risks

E0F3: `E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348`, title `0400486024DEC000`. **Do not claim 33FA support** or publish a speculative IPS for it. No repeated baseline GDB captures are necessary.

The user observed normal-looking gameplay even around 10–15 FPS. The helper's 4.0 step cap would mathematically limit a *single-update-per-render* engine at sustained 10 FPS to 40/60 nominal simulation units/second; the actual update cadence relative to the FPS overlay was not measured. Do not dismiss the user's observation or promise universally exact sub-15 FPS tracking. Future targeted validation, if needed, is for extended frame stalls, loading, menus/cutscenes and collision behavior, not another broad timer investigation.

## Historical research and clean-up

The long `HANDOFF.md`, V9 failure evidence, controller/code-window inspections, ZBIC decoding notes, synthetic debugger tools and dozens of one-off tests remain in **[historical snapshot 8fbda375](https://github.com/TheCraZyDuDee/Ocarina-of-Time-Remake-Mods/tree/8fbda375afd9236075b34d433644258de80aed36/mods/fps/research/true-dynamic)**. They were removed from the current release tree to keep it maintainable; Git history retains them. This handoff retains the research context. Current implementation details are in the [technical notes](../../fps/true-dynamic.md).

The original Nintendo instruction windows, NSOs and private debugger logs have **never been added to GitHub**. Avoid changing the golden release patch while it is working.
