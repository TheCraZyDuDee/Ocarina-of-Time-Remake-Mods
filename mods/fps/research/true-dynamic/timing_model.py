"""Source-only model of fixed 60 Hz simulation against variable presentation.

NOT an IPS generator or proof of Ocarina gameplay behavior. A real game patch
requires a safe update-loop hook for physics, animation, menu, and scene state.
No game files or third-party emulator source are used.
"""
from dataclasses import dataclass

TICKS_PER_SECOND = 60
NANOSECONDS_PER_SECOND = 1_000_000_000


@dataclass(frozen=True)
class FramePlan:
    fixed_updates: int
    pending_whole_updates: int
    pending_fractional_update: float
    caught_up: bool


class FixedStepClock:
    """Model bounded fixed-step catch-up, not a working engine modification.

    A per-frame substep budget prevents unbounded CPU work but can make a game
    fall behind real time at very low FPS. Backlog remains until processed or
    explicitly reset by a scene transition. No silent elapsed-time discard.
    """

    def __init__(self, max_updates_per_frame: int = 12) -> None:
        if max_updates_per_frame < 1:
            raise ValueError("max_updates_per_frame must be positive")
        self.max_updates_per_frame = max_updates_per_frame
        self._pending_units = 0
        self.total_updates = 0

    def reset_after_loading(self) -> None:
        self._pending_units = 0

    def advance(self, elapsed_ns: int) -> FramePlan:
        if not isinstance(elapsed_ns, int) or elapsed_ns < 0:
            raise ValueError("elapsed_ns must be a nonnegative integer")
        self._pending_units += elapsed_ns * TICKS_PER_SECOND
        wanted = self._pending_units // NANOSECONDS_PER_SECOND
        steps = min(wanted, self.max_updates_per_frame)
        self._pending_units -= steps * NANOSECONDS_PER_SECOND
        self.total_updates += steps
        whole, fractional = divmod(self._pending_units, NANOSECONDS_PER_SECOND)
        return FramePlan(
            fixed_updates=steps,
            pending_whole_updates=whole,
            pending_fractional_update=fractional / NANOSECONDS_PER_SECOND,
            caught_up=whole == 0,
        )


def naive_speed_ratio(render_fps: float, game_step_ticks: float) -> float:
    """Why decoupling presentation from a fixed simulation step speeds up OoT."""
    if render_fps < 0 or game_step_ticks < 0:
        raise ValueError("FPS and ticks cannot be negative")
    return render_fps * game_step_ticks / TICKS_PER_SECOND


def emulate_fps(clock: FixedStepClock, rate: int, frames: int) -> list[FramePlan]:
    """Generate exact cumulative timestamps to avoid rounding drift."""
    if rate <= 0 or frames < 0:
        raise ValueError("rate must be > 0 and frames must be >= 0")
    result = []
    previous = 0
    for index in range(1, frames + 1):
        timestamp = (index * NANOSECONDS_PER_SECOND) // rate
        result.append(clock.advance(timestamp - previous))
        previous = timestamp
    return result
