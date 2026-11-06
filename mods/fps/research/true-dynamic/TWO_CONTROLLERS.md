# Two frame-rate controllers — verified static findings

**Research only. No IPS in this folder.** Both original decompressed OoT NSO
builds were checked locally with segment SHA-256 digests and exact ARM64
instruction fingerprints.

## Two paths reaching the same FPS setter

| Research label | E0F3 build (main+) | 33FA build (main+) |
| --- | --- | --- |
| FPS-target controller | `0x004DBDA0` | `0x0045DA10` |
| Interval-based controller | `0x03B4EF60` | `0x03AF18F0` |
| Shared FPS setter | `0x004DC0F0` | `0x0045DD60` |

- The **FPS-target controller** measures two frame-duration values, derives an
  FPS target from the larger estimate and calls the shared FPS setter.
- The **interval controller** measures comparable durations, selects integer
  60-Hz ticks per draw, calls the same FPS setter with `60 / interval`, and
  also calls a separate presentation/swap setter. Earlier fixed-30 and
  adaptive IPS patches modify this interval controller.
- Both functions are reached via indirect dispatch; no direct callsites
  establish which one executes during menus or gameplay. **Do not claim
  both are active solely because both are present.**

Verified direct call edges (module offsets):

| Call edge | E0F3 | 33FA |
| --- | --- | --- |
| FPS controller to shared setter | `0x004DBDF8 -> 0x004DC0F0` | `0x0045DA68 -> 0x0045DD60` |
| Interval controller to shared setter | `0x03B4F190 -> 0x004DC0F0` | `0x03AF1B20 -> 0x0045DD60` |
| Interval controller to presentation | `0x03B4F088 -> 0x0346C5C0` | `0x03AF1A18 -> 0x0340B950` |

## General FPS validation is not arbitrary

The shared setter checks for an exact divisor of 60 Hz. When the requested
FPS does not divide 60, it returns an unsuccessful result and provides a
lower suggestion through an optional output parameter. Examples from the
game's arithmetic:

| Request | General-path suggestion |
| --- | --- |
| 59, 45, 40, 37 | 30 FPS |
| 25 | 20 FPS |
| 17 | 15 FPS |
| 14 | 12 FPS |

A **special 40+ FPS path** exists, guarded by `object[0x231] == 1` and
`object[0x232] & 1`. It reaches a different rate-setting path before
the exact-divisor test. **What those flags mean, whether this mode is
enabled, and whether the downstream callbacks permit intermediate rates
are not established.** Patching flags blindly risks repeating V7's failure.

See [the independent validation model](frame_rate_acceptance.py) and
[read-only control-flow mapper](map_time_managers.py). Neither writes a
game patch. Their tests require no copyrighted game files.

## Implications for a future mod

V8A changed presentation without independently verifying its simulation
time base; this explains a plausible over-speed mechanism but is **not
proof** that the second controller executes simultaneously. Further work:

1. Identify the actual *per-rendered-frame simulation update dispatcher*
   and the consumers of the FPS setter result, including menus.
2. Verify which controller runs at boot, in menus, after save loading, and
   during gameplay; ideally use emulator-side logging rather than risky
   guest-code injection.
3. Test whether bounded fixed 1/60-second substeps can execute within one
   rendered frame, without duplicating presentation or starving CPU work.
4. Confirm elapsed-time measurements include GPU waits and vblank pacing;
   distinguish frame processing cost from actual wall-clock frame duration.
5. Only then build a new, separate IPS for both executable versions,
   preserving all original register and lifecycle semantics.

Mario Kart World's [Lichii implementation](https://github.com/zortos293/Lichii/blob/main/src/core/loader/nso.cpp)
shows a useful *pattern*: enabling its native dynamic mode and switching
to whole-frame time, with a coordinated [present pacer](https://github.com/zortos293/Lichii/blob/main/src/core/hle/service/nx2_gsv.h).
Those instructions/offsets are **not transferable** to Ocarina.

At literally 0 FPS a render-driven update loop does not progress; real
simulation independence requires decoupled update scheduling.

All material here is newly written research code and brief compatibility
data. No Nintendo executable, private dump, keys, or GPL emulator source
is committed.
