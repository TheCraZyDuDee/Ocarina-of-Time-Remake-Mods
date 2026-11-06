# E0F3 frame-step branch graph: the two config calls are separate paths

**2026-11-06. Source-only research; no IPS or gameplay change.**

This note is based on an offline AArch64 control-flow graph built from
the tester's two **private, SHA-256-verified** E0F3 instruction windows:
`frame_step_window.json` (1024 bytes starting at
`main+0x006E6BE0`) and `frame_step_followup.json`
(continuation of 1792 bytes starting at `main+0x006E6FE0`).
The combined **2816-byte contiguous function excerpt** remains
private. Neither JSON nor any proprietary full instruction sequences
were committed.

## Important correction to the informal, initially linear reading

The original code at `main+0x006E6CC8` implements
**`TBNZ W9,#1,main+0x006E6D18`**, where `W9` is a prior snapshot
of `frame_context+0xD38` flags.

- With **bit 1 clear**, control falls through and can reach the
  **first** accounting and timing-config call path:
  atomic `+1` at `+0xD50` (`main+0x006E6CF8`),
  double `+S8` at `+0xD58`, then
  `BL main+0x03B4E300` at `main+0x006E6DD8`.
- With **bit 1 set**, control branches past the first accounting site
  and can reach the **second** path:
  atomic `+1` at `+0xD50` (`main+0x006E70C8`),
  double `+S8` at `+0xD58`, then
  `BL main+0x03B4E300` at `main+0x006E70F8`.

This is consistent with the prior eight-hit original-game breakpoint
trace: **all eight hits were at the second callsite**, with flags
`0x0B`, whose **bit 1 is set**. Both the first and second paths use
the same *kind* of atomic increment and double accumulation.

A crucial static distinction: **instruction order is not execution
order**. The first path's later code contains jumps that bypass the
second path. The verified in-window graph finds:

| Source | Destination | Reachability in captured code |
| --- | --- | --- |
| Bit-1-clear fallthrough after gate | First callsite | **Reachable** |
| Bit-1-set branch target | Second callsite | **Reachable** |
| Immediately after first call | Second callsite | **Not reachable** |
| Immediately after second call | First callsite | **Not reachable** |

The graph treats ordinary `BL` calls as returning to the following
instruction and walks AArch64 direct `B`, `B.cond`,
`CBZ/CBNZ`, `TBZ/TBNZ` and fallthrough edges, stopping at
`RET` and indirect `BR`. It does **not** model callbacks that
alter control flow nonlocally, concurrent threads, or branches to code
outside the bounded excerpt. Consequently the supported conclusion
is that **the captured function does NOT establish double accounting
per single invocation**; in fact, each observed ordinary path reaches
its own callsite, not both. A second invocation on a different path,
other engine work, or unrelated counters are outside this proof.

**This explicitly corrects any previous speculation that the first
callsite necessarily falls through to the second.** Do not use
"two sites means two updates per present" as a V9 failure theory.

## Explaining flags 0x0B versus 0x2B

Both `0x0B` and `0x2B` have **bit 1 set**; they should select
the same second accounting path at the gate. Their difference is
**bit 5** (`0x20`).

On the second-path preamble, the original code performs an atomic
`LDSET` of bit 5 at `main+0x006E6D24` around an update/callback
sequence, then an atomic `LDCLR` of bit 5 at
`main+0x006E6D48`. Thus the earlier sporadic `0x2B`
snapshots are consistent with a **transient in-progress bit** rather
than necessarily a different FPS mode or the earlier caller branch.
The exact meaning, all writers, and transitions outside the captured
function remain unknown.

## Impact on V9 investigation

This removes a weaker suspected root cause: ordinary execution of
the first path followed immediately by the second within the same
function invocation is **not supported by static reachability**.
V9's three separate changes (guard, presentation argument and step)
still require causal isolation. The original active gameplay path
and `+S8` accounting are documented, but no evidence establishes
whether V9 itself changed the bit-1 branch, callback, or cadence.
The next useful evidence is what the optional config callback actually
does and whether the native pacing code applies the transient
`60/S8` nominal rate. A guarded callback pointer resolver has been
prepared, but user participation is not required for further
source-only research.

Never commit private executable bytes; keep stable `main` and
releases unchanged. Base 33FA has not been independently mapped to
this graph.
