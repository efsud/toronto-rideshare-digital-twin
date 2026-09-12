"""Minimal marketplace simulation engine with policy and routing hooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.marketplace.matching import RoutingContext, greedy_match
from toronto_rideshare.policies.behavior import BehaviorConfig
from toronto_rideshare.policies.registry import PolicySettings, zone_adjustments_from_imbalance
from toronto_rideshare.policies.repositioning import suggest_reposition_targets
from toronto_rideshare.simulation.clock import SimulationClock
from toronto_rideshare.simulation.imbalance import zone_demand_supply
from toronto_rideshare.simulation.waiting import WaitingTimeTracker
from toronto_rideshare.supply.models import Driver, DriverStatus


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
    routing: RoutingContext | None = None
    policy_settings: PolicySettings | None = None
    behavior: BehaviorConfig | None = None
    policy_cfg: dict[str, Any] = field(default_factory=dict)
    reposition_events: int = 0
    _trip_index: int = 0

    def run(self) -> SimulationMetrics:
        self.clock.reset()
        pending: list[TripRequest] = []
        settings = self.policy_settings

        while True:
            while (
                self._trip_index < len(self.trips)
                and self.trips[self._trip_index].request_time_min <= self.clock.current_time_min
            ):
                pending.append(self.trips[self._trip_index])
                self._trip_index += 1

            zone_adjustments: dict[str, tuple[float, float]] | None = None
            if settings and (
                settings.use_rider_pricing
                or settings.use_driver_bonuses
                or settings.use_ortools
            ):
                imbalance = zone_demand_supply(pending, self.drivers)
                zone_adjustments = zone_adjustments_from_imbalance(
                    imbalance, settings, self.policy_cfg
                )

            if settings and settings.use_repositioning:
                imbalance = zone_demand_supply(pending, self.drivers)
                assignments = suggest_reposition_targets(self.drivers, imbalance)
                self.reposition_events += len(assignments)
                for driver in self.drivers:
                    if driver.status == DriverStatus.REPOSITIONING:
                        driver.status = DriverStatus.IDLE

            for driver in self.drivers:
                if (
                    driver.status == DriverStatus.WITH_RIDER
                    and driver.available_time_min <= self.clock.current_time_min
                ):
                    driver.status = DriverStatus.IDLE

            matches = greedy_match(
                pending,
                self.drivers,
                self.clock.current_time_min,
                routing=self.routing,
                zone_adjustments=zone_adjustments,
            )
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
