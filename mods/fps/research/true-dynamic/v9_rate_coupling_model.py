#!/usr/bin/env python3
"""Offline mathematical audit of archived, failed V9's fractional step.

This is NOT a game mod, a V10 prototype, or a reliable frame-rate
prediction. It reproduces V9's floating-point conversion/clamp and the
E0F3 config converter's nominal 60 / step rounding, using independent
test values (not proprietary game bytes). It does NOT model the native
FPS setter's callback path, native presentation pacing or engine physics.
"""
import argparse
import json
import math
import struct

COUNTER_HZ = 31_250_000
GENERAL_FPS_DIVISORS = frozenset(d for d in range(1, 61) if 60 % d == 0)


def float32(value):
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def v9_step_from_ticks(ticks, *, base=60, frequency=COUNTER_HZ):
    if not isinstance(ticks, int) or ticks < 0 or ticks >= (1 << 63):
        raise ValueError("Ticks must be a nonnegative signed-64-bit integer")
    if not isinstance(base, int) or base <= 0:
        raise ValueError("Base rate must be positive integer")
    if not isinstance(frequency, int) or frequency <= 0:
        raise ValueError("Frequency must be positive integer")
    # Archived V9 uses SCVTF (int->single), then FMUL and FDIV in
    # single precision, followed by FMAXNM 0.5 and FMINNM 4.0.
    ticks_as_float = float32(ticks)
    base_float = float32(base)
    frequency_float = float32(frequency)
    delta = float32(float32(ticks_as_float * base_float) / frequency_float)
    return float32(min(4.0, max(0.5, delta)))


def nominal_rate_from_step(step):
    if not math.isfinite(step) or step <= 0:
        raise ValueError("Step must be positive and finite")
    # Approximate ordinary positive-rate path. The original converter
    # uses truncation plus a threshold comparison for fractional parts.
    quotient = float32(float32(60.0) / float32(step))
    return math.floor(quotient + 0.5)


def diagnostic_for_ticks(ticks):
    step = v9_step_from_ticks(ticks)
    nominal = nominal_rate_from_step(step)
    return {
        "input_ticks": ticks,
        "v9_step": step,
        "hypothetical_nominal_rate": nominal,
        "accepted_by_general_divisor_rule": nominal in GENERAL_FPS_DIVISORS,
        "disclaimer": "Math only; no live V9 callback, presentation or gameplay rate validated."
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("ticks", nargs="+", type=int,
                   help="Hypothetical counter-tick deltas; not live game captures")
    args = p.parse_args()
    print(json.dumps([diagnostic_for_ticks(t) for t in args.ticks],
                     indent=2))


if __name__ == "__main__":
    main()
