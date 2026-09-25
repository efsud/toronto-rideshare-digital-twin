"""Simulation time clock."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class SimulationClock:
    """Discrete simulation clock in minutes from start."""

    start_time_min: float = 0.0
    end_time_min: float = 180.0
    step_min: float = 5.0
    current_time_min: float = 0.0

    def __post_init__(self) -> None:
        if not all(
            math.isfinite(x) for x in (self.start_time_min, self.end_time_min, self.step_min)
        ):
            raise ValueError("Clock values must be finite")
        if self.step_min <= 0 or self.end_time_min < self.start_time_min:
            raise ValueError("Positive step and ordered horizon required")

    def reset(self) -> None:
        self.current_time_min = self.start_time_min

    def advance(self) -> bool:
        """Advance one step; return False if past end."""
        self.current_time_min = min(self.end_time_min, self.current_time_min + self.step_min)
        return self.current_time_min <= self.end_time_min
