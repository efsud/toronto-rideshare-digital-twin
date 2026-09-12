"""Minimal marketplace simulation engine (baseline P0)."""

from __future__ import annotations

from dataclasses import dataclass, field

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.marketplace.matching import greedy_match
from toronto_rideshare.simulation.clock import SimulationClock
from toronto_rideshare.simulation.waiting import WaitingTimeTracker
from toronto_rideshare.supply.models import Driver


@dataclass
class SimulationMetrics:
    completed_trips: int = 0
    unserved_trips: int = 0
    total_rider_payment_cad: float = 0.0
    total_driver_earnings_cad: float = 0.0


@dataclass
class SimulationEngine:
    clock: SimulationClock
    drivers: list[Driver]
    trips: list[TripRequest]
    waiting: WaitingTimeTracker = field(default_factory=WaitingTimeTracker)
    metrics: SimulationMetrics = field(default_factory=SimulationMetrics)
    _trip_index: int = 0

    def run(self) -> SimulationMetrics:
        self.clock.reset()
        pending: list[TripRequest] = []
        while True:
            while (
                self._trip_index < len(self.trips)
                and self.trips[self._trip_index].request_time_min <= self.clock.current_time_min
            ):
                pending.append(self.trips[self._trip_index])
                self._trip_index += 1

            matches = greedy_match(pending, self.drivers, self.clock.current_time_min)
            for trip, _driver, pickup_min, _trip_min, fare in matches:
                pending.remove(trip)
                queue_wait = self.clock.current_time_min - trip.request_time_min
                self.waiting.start_queue(trip.request_id, queue_wait)
                self.waiting.add_pickup(trip.request_id, pickup_min)
                self.metrics.completed_trips += 1
                self.metrics.total_rider_payment_cad += fare.rider_payment_cad
                self.metrics.total_driver_earnings_cad += fare.driver_earnings_cad

            if not self.clock.advance():
                break

        self.metrics.unserved_trips = len(pending)
        return self.metrics
