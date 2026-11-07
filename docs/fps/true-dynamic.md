# True Dynamic FPS: technical notes

The current E0F3 patch is the isolated simulation-step patch from the V10 playtest. A tester reported normal-looking gameplay at about 10–15 and 30–45 FPS under Eglantine. Update cadence and whole-game timing haven't been measured independently.

## Patch layout

The hook replaces `FDIV S8,S1,S0` at `main+0x006E6CC4`. A 16-instruction helper reads the physical-counter frame delta from the game's timing state at `+0x100`, scales it using the nominal frequency and `CNTFRQ_EL0`, and clamps the result to 0.5–4.0 simulation units per update.

Control flow:

`0x006E6CC4 → 0x006E1864 → 0x006E0F04 → 0x006F1804 → 0x006E6CC8`

The helper and trampoline use padding verified during the original research. The controller guard at `main+0x03B4EF90` and presentation load at `main+0x03B4F080` stay untouched. Earlier V9 changes included those sites and ran too fast.

The timing callback at `main+0x02F52DF0` uses the variable step for some object countdown and interpolation work. This doesn't establish correctness for every game system.

## Release checks

The IPS contains 20 records and is 209 bytes. Its SHA-256 is:

```text
306e36cec3efc28a38df627ed38245fe29008855a85cfe4a249a7d8fb2fd1365
```

The generator and tests pin that hash. Preserve it unless a replacement has been independently tested. ZIP packaging can change without changing the IPS payload.

Only E0F3 is supported. A 33FA port needs its own address verification and playtesting.

## Remaining questions

The 4.0 step cap could limit timing recovery below 15 FPS if there is one update per rendered frame. The relationship between the FPS overlay and update cadence wasn't measured, so the tester's observations don't establish exact wall-clock timing at sustained low FPS.

Useful follow-up tests cover extended stalls, loading, menus, cutscenes and collision behavior.

[Source](../../mods/fps/build.py) · [Research history](../ai/fps/true-dynamic.md) · [Development guide](../DEVELOPMENT.md)
