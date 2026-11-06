"""Offline model explaining why V9 could run too fast.

It does not read or modify a game and cannot determine actual runtime fields.
"""
from dataclasses import dataclass

HZ = 60
GUEST_COUNTER_HZ = 31_250_000


def clamp(value: float, lo: float = 0.5, hi: float = 4.0) -> float:
    if not lo <= hi:
        raise ValueError("invalid clamp")
    return max(lo, min(hi, value))


def v9_step_from_ticks(frame_tick_value: float, nominal_hz: int = HZ,
                       counter_hz: int = GUEST_COUNTER_HZ) -> float:
    if frame_tick_value < 0 or nominal_hz <= 0 or counter_hz <= 0:
        raise ValueError("invalid clock parameters")
    return clamp(nominal_hz * frame_tick_value / counter_hz)


def implied_game_speed(rendered_fps: float, ticks_per_frame: float,
                       nominal_hz: int = HZ) -> float:
    """Return speed factor (1.0 = real-time) for a per-render update loop."""
    if rendered_fps < 0 or ticks_per_frame < 0 or nominal_hz <= 0:
        raise ValueError("invalid speed parameters")
    return rendered_fps * ticks_per_frame / nominal_hz


def threshold_ticks(nominal_hz: int = HZ,
                    counter_hz: int = GUEST_COUNTER_HZ) -> float:
    return 4 * counter_hz / nominal_hz


def expected_duration_ticks(rendered_fps: float,
                            counter_hz: int = GUEST_COUNTER_HZ) -> float:
    if rendered_fps <= 0:
        raise ValueError("rendered FPS must be positive")
    return counter_hz / rendered_fps
