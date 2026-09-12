"""Simulation time clock."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SimulationClock:
    """Discrete simulation clock in minutes from start."""

    start_time_min: float = 0.0
    end_time_min: float = 180.0
    step_min: float = 5.0
    current_time_min: float = 0.0

    def reset(self) -> None:
        self.current_time_min = self.start_time_min

    def advance(self) -> bool:
        """Advance one step; return False if past end."""
        self.current_time_min += self.step_min
        return self.current_time_min <= self.end_time_min
