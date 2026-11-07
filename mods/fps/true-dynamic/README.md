# True Dynamic FPS

Adjusts the game's simulation timing as the frame rate changes, while leaving its frame-rate controller and presentation interval alone.

[Download True Dynamic FPS](../../../releases/oot-true-dynamic-e0f3.zip?raw=true)

## Compatibility

Supports **E0F3 only**: `E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348`.

The 33FA base build and other versions aren't supported.

## What to expect

A tester using Eglantine reported normal-looking gameplay speed at around **10–15 and 30–45 FPS**. This is still experimental: physics, cutscenes and every scene haven't been independently timed.

The timing adjustment has a limit, so long stalls or sustained very low FPS may still slow the game down. The mod doesn't add frame generation or increase emulator speed.

## Install

Follow the [FPS installation guide](../README.md#installation). Disable all other FPS patches, including older dynamic experiments, and keep emulator speed at 100% with frame generation off.

If menus, loading, collisions, animations or cutscenes behave oddly, disable the mod and report where it happened.

## Source

Built by [the shared FPS generator](../build.py) with `--mode true-dynamic`. The release keeps the same 209-byte patch used in the successful V10 playtest.

[Technical notes](../../../docs/fps/true-dynamic.md) · [Compare FPS mods](../README.md) · [Project home](../../../README.md)
