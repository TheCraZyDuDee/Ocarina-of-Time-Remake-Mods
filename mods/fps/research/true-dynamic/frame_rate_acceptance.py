"""Offline model of frame-rate setter validation; not a game patch or engine.

The original binaries contain a special 40+ FPS branch guarded by byte flags
at object offsets +0x231 and +0x232. Their meanings are unknown.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class RateDecision:
    accepted_by_initial_guard: bool
    suggested_lower_fps: int | None
    path: str

def decide(requested_fps: int, mode_byte_is_one: bool=False,
           capability_bit_set: bool=False) -> RateDecision:
    if not isinstance(requested_fps,int):
        raise TypeError("requested FPS must be an integer")
    if requested_fps <= 0:
        return RateDecision(False,None,"rejected nonpositive rate")
    if mode_byte_is_one and capability_bit_set and requested_fps>=40:
        return RateDecision(True,None,"special 40+ path; later callback result unknown")
    if 60 % requested_fps==0:
        return RateDecision(True,None,"exact 60Hz divisor")
    ceil_ticks=(60+requested_fps-1)//requested_fps
    suggested=60//ceil_ticks
    return RateDecision(False,suggested,"nondivisor; returned suggestion")
