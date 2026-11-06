# First experimental dynamic-FPS build: readiness and validation gates

**As requested by the tester: when research supports it, produce the first
actual installable mod build—not just another analysis note.**

The first *experimental* build is deliberately an **isolated step**
experiment on **E0F3 only**. It must never be silently published to
`main`/stable releases or represented as a tested fix. The longer-term
goal remains dynamic FPS without slow-motion or sped-up gameplay at
variable *actual* rendering rates.

## Source-level evidence available (2026-11-06)

1. Original unmodified gameplay at approximately 30 actual FPS runs in
   slow motion. The original timing configuration remains
   `step=1.0`, nominal=60, and the frame-context counters progress
   at ~30 units per requested free-running second.
2. Original `X21+0x100` is a frame-like guest physical counter delta,
   averaging 33.450 ms in sparse original ~30 FPS gameplay samples.
   The ~50 FPS capture also scales plausibly. It cannot be treated
   as a cumulative 4-clamp timer on the basis of those samples.
3. The original frame-step hook at E0F3 `main+0x006E6CC4`
   produces `S8=1.0` for 60 nominal FPS, and feeds
   `main+0x03B4E300` timing config on the active call path.
4. The callback is **present** and the newly verified 4096-byte
   `main+0x02F52DF0` source window shows it loads the variable
   step from config`+0x10`, rounds steps for integer object
   countdowns, performs step-multiplied float interpolation,
   and computes other event/time-scale values. Thus fractional or
   multi-unit steps have explicit downstream implementations,
   although not all whole-engine physics is verified.
5. The native presentation setter at `main+0x0346C5C0` both sends
   the argument interval to a lower-level setter and writes
   **`timing+0xFC = 60/interval`** (60 when interval=0).
6. V9 changed *three* sites: original guard, presentation argument
   and frame-step divide. Its forced present interval 1 could
   contradict rate setting derived from stored interval. Its
   over-speed is real and should not be repeated.
7. Original native FPS setter at `main+0x004DC0F0` has the
   normal divisor-of-60 rule and a special state-gated branch
   accepting some >=40 requests without that ordinary test.

## Candidate and guardrails

[`isolated_step_research_builder.py`](isolated_step_research_builder.py)
is a **source-only, opt-in prototype builder** that reuses the
archived, original-GDB-data-based V9 *simulation-step helper* while
intentionally omitting the two unverified V9 controller edits:

| Location | Failed V9 | Isolated research prototype |
| --- | --- | --- |
| E0F3 `main+0x03B4EF90` | Replaced TBNZ with NOP | **Keep original branch** |
| E0F3 `main+0x03B4F080` | Forced W1=1 | **Keep original interval load** |
| E0F3 `main+0x006E6CC4` | Wall-clock step helper | Same research helper, guarded |
| Isolated zero-filled executable caves | Helper code | Verified private trampoline only |

The code verifies the NSO's exact original E0F3 SHA-256 segment hashes,
the original hook/neighbor instruction fingerprints, both unchanged
controller instruction fingerprints, isolated code-cave zeros,
range-checked direct branches and IPS ZIP roundtrip. No game executable
is packaged. Requires user's original **decompressed** (not ZBIC)
E0F3 NSO. It will refuse to overwrite an existing private ZIP.

The source tests `tests/test_isolated_step_research_builder.py` are
synthetic and check no controller instructions are touched, cave errors
fail closed, and the archive stays clean. **No actual IPS has been
produced from the user's NSO in this research session** because the
uploaded private NSOs are ZBIC-compressed and the required ZBIC-aware
decoder is not installed. Recreating a build without exact source
verification would be worse than deferring generation.

## Gates before calling the build ready for tester evaluation

- [x] Original E0F3 hook and rate/presentation controller effects
  identified from private SHA-256-verified source windows.
- [x] Variable-step consumer confirmed in callback code.
- [x] V9 unrelated guard and presentation edits are excluded from
  the new source-only prototype.
- [x] Prototype source and synthetic tests committed only on
  `research/true-dynamic-fps`.
- [ ] Obtain original decompressed/verified E0F3 NSO privately,
  either by a working ZBIC extraction of user's existing originals
  or by local preparation on the user's Linux setup. Do not publish it.
- [ ] Build and independently audit the real E0F3 IPS patch ZIP
  from that private file; verify installed patch has only intended
  source modifications and branches.
- [ ] Tester validates baseline and isolated prototype with backed-up
  saves at approx. 60, 45, 30 and 15 actual FPS, plus loading/menus.
  Check real-world elapsed time, animation/physics/collision and
  audio behavior, not just an FPS overlay.
- [ ] Fix any failures before generating a first *usable* dynamic
  FPS release; map and validate 33FA independently.

**User instruction:** once these research and packaging prerequisites
are met, actually produce the first installable build for testing;
do not indefinitely substitute additional documents for the mod.
No build goes on stable main or release without empirical validation.
