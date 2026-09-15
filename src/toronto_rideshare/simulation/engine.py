"""Step-observable discrete marketplace simulation engine."""

from __future__ import annotations

import copy
import random
from dataclasses import asdict, dataclass, field
from typing import Any

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.marketplace.fares import compute_fare
from toronto_rideshare.marketplace.matching import (
    RoutingContext,
    batch_assign,
    estimate_route,
    min_to_departure_time,
    pickup_candidates,
)
from toronto_rideshare.policies.behavior import (
    BehaviorConfig,
    OfferAcceptanceConfig,
    apply_driver_bonus_response,
    driver_accepts_reposition,
    driver_offer_probability,
    rider_request_probability,
)
from toronto_rideshare.policies.registry import PolicySettings, zone_adjustments_from_imbalance
from toronto_rideshare.policies.repositioning import suggest_reposition_targets
from toronto_rideshare.simulation.clock import SimulationClock
from toronto_rideshare.simulation.imbalance import zone_demand_supply
from toronto_rideshare.simulation.waiting import WaitingTimeTracker
from toronto_rideshare.supply.models import Driver, DriverStatus
from toronto_rideshare.zones import zone_center


@dataclass
class SimulationMetrics:
    completed_trips: int = 0
    unserved_trips: int = 0
    total_rider_payment_cad: float = 0.0
    total_driver_earnings_cad: float = 0.0
    platform_net_revenue_cad: float = 0.0
    rejected_offers: int = 0
    accepted_offers: int = 0
    total_offers: int = 0
    subsidy_spend_cad: float = 0.0
    optimization_steps: int = 0
    cancelled_trips: int = 0
    rider_price_declines: int = 0
    unserved_arrived_trips: int = 0
    not_yet_released_trips: int = 0
    in_progress_trips: int = 0
    assigned_trips: int = 0
    total_queue_wait_min: float = 0.0
    total_pickup_time_min: float = 0.0
    total_trip_time_min: float = 0.0
    total_reposition_time_min: float = 0.0
    mean_wait_min: float = 0.0
    mean_pickup_time_min: float = 0.0
    mean_trip_time_min: float = 0.0
    acceptance_rate: float = 0.0
    service_rate: float = 0.0
    utilization_rate: float = 0.0
    routing_mode_counts: dict[str, int] = field(default_factory=dict)


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
    acceptance: OfferAcceptanceConfig = field(default_factory=OfferAcceptanceConfig)
    random_seed: int = 42
    policy_cfg: dict[str, Any] = field(default_factory=dict)
    matching_strategy: str | None = None
    max_wait_time_min: float = 15.0
    reposition_events: int = 0
    _trip_index: int = 0
    pending: list[TripRequest] = field(default_factory=list, init=False)
    events: list[dict[str, Any]] = field(default_factory=list, init=False)
    last_snapshot: dict[str, Any] = field(default_factory=dict, init=False)
    finished: bool = field(default=False, init=False)
    _initial_drivers: list[Driver] = field(default_factory=list, init=False, repr=False)
    _rng: random.Random = field(init=False, repr=False)
    _active_movements: dict[str, dict[str, Any]] = field(
        default_factory=dict, init=False, repr=False
    )
    _last_adjustments: dict[str, tuple[float, float]] = field(
        default_factory=dict, init=False, repr=False
    )
    _behavior_evaluated: set[str] = field(default_factory=set, init=False, repr=False)
    _routing_mode: str = field(default="haversine fallback", init=False, repr=False)
    _routing_fallback_reason: str | None = field(default=None, init=False, repr=False)
    _last_assignment_backend: str = field(default="greedy", init=False, repr=False)

    def __post_init__(self) -> None:
        self.trips.sort(key=lambda trip: (trip.request_time_min, trip.request_id))
        self._initial_drivers = copy.deepcopy(self.drivers)
        self._rng = random.Random(self.random_seed)
        self.reset()

    def reset(self) -> dict[str, Any]:
        """Restore initial agents and return a serializable initial snapshot."""
        self.clock.reset()
        self.drivers[:] = copy.deepcopy(self._initial_drivers)
        self.waiting = WaitingTimeTracker()
        self.metrics = SimulationMetrics()
        self.reposition_events = 0
        self._trip_index = 0
        self.pending = []
        self.events = []
        self._active_movements = {}
        self._last_adjustments = {}
        self._behavior_evaluated = set()
        self._routing_mode = (
            "time-dependent network"
            if self.routing and self.routing.profile and self.routing.use_time_dependent
            else "network free-flow"
            if self.routing
            else "haversine fallback"
        )
        self._routing_fallback_reason = (
            None if self.routing else "no routing context configured"
        )
        self._last_assignment_backend = "greedy"
        self.finished = False
        self._rng = random.Random(self.random_seed)
        self.last_snapshot = self.snapshot([])
        return self.last_snapshot

    def run(self) -> SimulationMetrics:
        """Reset and run all decision epochs, preserving the original API."""
        self.reset()
        while not self.finished:
            self.step()
        return self.metrics

    def _record_route(self, route: Any) -> None:
        self._routing_mode = route.mode
        counts = self.metrics.routing_mode_counts
        counts[route.mode] = counts.get(route.mode, 0) + 1
        if route.fallback_reason:
            self._routing_fallback_reason = route.fallback_reason

    def _refresh_derived_metrics(self) -> None:
        metrics = self.metrics
        metrics.in_progress_trips = sum(
            "request_id" in movement for movement in self._active_movements.values()
        )
        assigned = metrics.assigned_trips
        metrics.platform_net_revenue_cad = (
            metrics.total_rider_payment_cad - metrics.total_driver_earnings_cad
        )
        metrics.mean_wait_min = (
            metrics.total_queue_wait_min + metrics.total_pickup_time_min
        ) / assigned if assigned else 0.0
        metrics.mean_pickup_time_min = (
            metrics.total_pickup_time_min / assigned if assigned else 0.0
        )
        metrics.mean_trip_time_min = metrics.total_trip_time_min / assigned if assigned else 0.0
        metrics.acceptance_rate = (
            metrics.accepted_offers / metrics.total_offers if metrics.total_offers else 0.0
        )
        arrived = self._trip_index
        metrics.service_rate = metrics.completed_trips / arrived if arrived else 0.0
        elapsed = max(
            self.clock.step_min,
            min(self.clock.current_time_min, self.clock.end_time_min)
            - self.clock.start_time_min
            + self.clock.step_min,
        )
        capacity = len(self.drivers) * elapsed
        busy = (
            metrics.total_pickup_time_min
            + metrics.total_trip_time_min
            + metrics.total_reposition_time_min
        )
        metrics.utilization_rate = min(1.0, busy / capacity) if capacity else 0.0

    def _advance_movements(self, now: float, step_events: list[dict[str, Any]]) -> None:
        for driver in self.drivers:
            movement = self._active_movements.get(driver.driver_id)
            if movement is None:
                continue
            if driver.status == DriverStatus.EN_ROUTE_PICKUP and movement["pickup_time_min"] <= now:
                driver.lat, driver.lon = movement["origin"]
                driver.zone = movement["origin_zone"]
                driver.status = DriverStatus.WITH_RIDER
                driver.available_time_min = movement["end_time_min"]
                movement["phase"] = "with_rider"
                movement["start"] = movement["origin"]
                step_events.append(
                    {
                        "type": "pickup_completed",
                        "driver_id": driver.driver_id,
                        "request_id": movement["request_id"],
                    }
                )
            if driver.status == DriverStatus.WITH_RIDER and movement["end_time_min"] <= now:
                driver.lat, driver.lon = movement["destination"]
                driver.zone = movement["destination_zone"]
                driver.status = DriverStatus.IDLE
                driver.available_time_min = now
                self.metrics.completed_trips += 1
                self.metrics.total_rider_payment_cad += movement["rider_payment_cad"]
                self.metrics.total_driver_earnings_cad += movement["driver_earnings_cad"]
                self.metrics.subsidy_spend_cad += movement["subsidy_cad"]
                self._active_movements.pop(driver.driver_id)
                step_events.append(
                    {
                        "type": "trip_completed",
                        "driver_id": driver.driver_id,
                        "request_id": movement["request_id"],
                    }
                )
            elif (
                driver.status == DriverStatus.REPOSITIONING
                and movement["end_time_min"] <= now
            ):
                driver.lat, driver.lon = movement["destination"]
                driver.zone = movement["destination_zone"]
                driver.status = DriverStatus.IDLE
                driver.available_time_min = now
                self._active_movements.pop(driver.driver_id)
                step_events.append(
                    {"type": "reposition_completed", "driver_id": driver.driver_id}
                )

    def step(self) -> dict[str, Any]:
        """Process exactly one decision epoch and return its state/events."""
        if self.finished:
            return self.last_snapshot
        now = self.clock.current_time_min
        step_events: list[dict[str, Any]] = []

        self._advance_movements(now, step_events)

        while (
            self._trip_index < len(self.trips)
            and self.trips[self._trip_index].request_time_min <= now
        ):
            trip = self.trips[self._trip_index]
            self.pending.append(trip)
            self._trip_index += 1
            step_events.append(
                {
                    "type": "request_arrived",
                    "request_id": trip.request_id,
                    "origin": [trip.origin_lat, trip.origin_lon],
                    "destination": [trip.destination_lat, trip.destination_lon],
                }
            )

        settings = self.policy_settings
        adjustments: dict[str, tuple[float, float]] = {}
        imbalance = zone_demand_supply(self.pending, self.drivers)
        if settings and (
            settings.use_rider_pricing or settings.use_driver_bonuses or settings.use_ortools
        ):
            adjustments = zone_adjustments_from_imbalance(imbalance, settings, self.policy_cfg)
            if settings.use_ortools:
                self.metrics.optimization_steps += 1
            step_events.append(
                {
                    "type": "policy_decision",
                    "optimization": settings.use_ortools,
                    "zone_adjustments": {
                        zone: {"rider_premium": values[0], "driver_bonus": values[1]}
                        for zone, values in adjustments.items()
                    },
                }
            )
        self._last_adjustments = adjustments

        for trip in list(self.pending):
            if now - trip.request_time_min >= self.max_wait_time_min:
                self.pending.remove(trip)
                self.metrics.cancelled_trips += 1
                self.metrics.unserved_trips += 1
                step_events.append(
                    {
                        "type": "request_cancelled",
                        "request_id": trip.request_id,
                        "wait_min": now - trip.request_time_min,
                        "reason": "max_wait_exceeded",
                    }
                )

        if settings and settings.use_behavior and self.behavior:
            for trip in list(self.pending):
                if trip.request_id in self._behavior_evaluated:
                    continue
                self._behavior_evaluated.add(trip.request_id)
                rider_adj = adjustments.get(trip.origin_zone, (0.0, 0.0))[0]
                probability = rider_request_probability(rider_adj, config=self.behavior)
                draw = self._rng.random()
                if draw >= probability:
                    self.pending.remove(trip)
                    self.metrics.rider_price_declines += 1
                    self.metrics.unserved_trips += 1
                    step_events.append(
                        {
                            "type": "rider_price_declined",
                            "request_id": trip.request_id,
                            "rider_adjustment_cad": rider_adj,
                            "probability": probability,
                            "draw": draw,
                        }
                    )

        if settings and settings.use_repositioning:
            assignments = suggest_reposition_targets(self.drivers, imbalance)
            by_id = {driver.driver_id: driver for driver in self.drivers}
            for driver_id, target_zone in sorted(assignments.items()):
                driver = by_id[driver_id]
                if settings.use_behavior and self.behavior and not driver_accepts_reposition(
                    config=self.behavior, rng_value=self._rng.random()
                ):
                    step_events.append(
                        {
                            "type": "reposition_rejected",
                            "driver_id": driver_id,
                            "target_zone": target_zone,
                        }
                    )
                    continue
                target = zone_center(target_zone)
                route = estimate_route(
                    (driver.lat, driver.lon),
                    target,
                    routing=self.routing,
                    departure_time=min_to_departure_time(now),
                )
                self._record_route(route)
                driver.status = DriverStatus.REPOSITIONING
                driver.available_time_min = now + route.travel_time_min
                self._active_movements[driver_id] = {
                    "driver_id": driver_id,
                    "phase": "repositioning",
                    "start_time_min": now,
                    "end_time_min": driver.available_time_min,
                    "start": [driver.lat, driver.lon],
                    "origin": [driver.lat, driver.lon],
                    "destination": list(target),
                    "destination_zone": target_zone,
                }
                self.reposition_events += 1
                self.metrics.total_reposition_time_min += route.travel_time_min
                step_events.append(
                    {
                        "type": "reposition_started",
                        "driver_id": driver_id,
                        "target_zone": target_zone,
                        "travel_time_min": route.travel_time_min,
                    }
                )

        available = [
            driver
            for driver in self.drivers
            if driver.status == DriverStatus.IDLE and driver.available_time_min <= now
        ]
        strategy = self.matching_strategy or (
            settings.matching_strategy if settings else "greedy"
        )
        preferred: dict[str, str] = {}
        if strategy == "optimal_batch":
            assignment = batch_assign(
                self.pending, available, now, routing=self.routing, use_ortools=True
            )
            preferred = {request_id: driver_id for request_id, driver_id, _ in assignment.pairs}
            self._last_assignment_backend = assignment.backend
            step_events.append(
                {
                    "type": "matching_decision",
                    "strategy": strategy,
                    "backend": assignment.backend,
                    "total_pickup_min": assignment.total_pickup_min,
                    "fallback_reason": assignment.fallback_reason,
                }
            )
        for trip in list(self.pending):
            candidates = pickup_candidates(trip, available, now, routing=self.routing)
            if trip.request_id in preferred:
                preferred_id = preferred[trip.request_id]
                candidates.sort(
                    key=lambda item: (item[1].driver_id != preferred_id, item[0], item[1].driver_id)
                )

            for pickup_min, driver, pickup_route in candidates:
                self._record_route(pickup_route)
                trip_route = estimate_route(
                    (trip.origin_lat, trip.origin_lon),
                    (trip.destination_lat, trip.destination_lon),
                    routing=self.routing,
                    departure_time=min_to_departure_time(now + pickup_min),
                )
                self._record_route(trip_route)
                trip_km, trip_min = trip_route.distance_km, trip_route.travel_time_min
                rider_adj, bonus = adjustments.get(trip.origin_zone, (0.0, 0.0))
                committed_subsidy = sum(
                    float(movement.get("subsidy_cad", 0.0))
                    for movement in self._active_movements.values()
                )
                remaining_budget = max(
                    0.0,
                    float(self.policy_cfg.get("subsidy_budget_cad", 500.0))
                    - self.metrics.subsidy_spend_cad
                    - committed_subsidy,
                )
                requested_subsidy = max(0.0, -rider_adj) + max(0.0, bonus)
                if requested_subsidy > remaining_budget and requested_subsidy > 0.0:
                    scale = remaining_budget / requested_subsidy
                    if rider_adj < 0.0:
                        rider_adj *= scale
                    bonus *= scale
                fare = compute_fare(
                    trip_km,
                    trip_min,
                    rider_adjustment_cad=rider_adj,
                    driver_bonus_cad=bonus,
                )
                probability = driver_offer_probability(
                    fare.driver_earnings_cad, pickup_min, config=self.acceptance
                )
                if settings and settings.use_behavior and self.behavior:
                    probability = apply_driver_bonus_response(
                        probability, bonus, config=self.behavior
                    )
                draw = self._rng.random()
                accepted = draw < probability
                offer = {
                    "type": "offer_accepted" if accepted else "offer_rejected",
                    "request_id": trip.request_id,
                    "driver_id": driver.driver_id,
                    "pickup_min": pickup_min,
                    "trip_min": trip_min,
                    "probability": probability,
                    "draw": draw,
                    "rider_payment_cad": fare.rider_payment_cad,
                    "driver_earnings_cad": fare.driver_earnings_cad,
                    "driver_bonus_cad": fare.driver_bonus_cad,
                    "origin": [trip.origin_lat, trip.origin_lon],
                    "destination": [trip.destination_lat, trip.destination_lon],
                }
                step_events.append(offer)
                self.metrics.total_offers += 1
                if not accepted:
                    self.metrics.rejected_offers += 1
                    continue

                self.metrics.accepted_offers += 1
                driver.status = DriverStatus.EN_ROUTE_PICKUP
                driver.available_time_min = now + pickup_min
                available.remove(driver)
                self.pending.remove(trip)
                self._active_movements[driver.driver_id] = {
                    "driver_id": driver.driver_id,
                    "request_id": trip.request_id,
                    "phase": "en_route_pickup",
                    "start_time_min": now,
                    "pickup_time_min": now + pickup_min,
                    "end_time_min": now + pickup_min + trip_min,
                    "start": [driver.lat, driver.lon],
                    "origin": [trip.origin_lat, trip.origin_lon],
                    "destination": [trip.destination_lat, trip.destination_lon],
                    "origin_zone": trip.origin_zone,
                    "destination_zone": trip.destination_zone,
                    "rider_payment_cad": fare.rider_payment_cad,
                    "driver_earnings_cad": fare.driver_earnings_cad,
                    "subsidy_cad": max(0.0, -fare.rider_adjustment_cad)
                    + max(0.0, fare.driver_bonus_cad),
                }
                queue_wait = now - trip.request_time_min
                self.waiting.start_queue(trip.request_id, queue_wait)
                self.waiting.add_pickup(trip.request_id, pickup_min)
                self.metrics.assigned_trips += 1
                self.metrics.total_queue_wait_min += queue_wait
                self.metrics.total_pickup_time_min += pickup_min
                self.metrics.total_trip_time_min += trip_min
                break

        self.events.extend({"time_min": now, **event} for event in step_events)
        if now >= self.clock.end_time_min:
            self.finished = True
            self.metrics.not_yet_released_trips = len(self.trips) - self._trip_index
            self.metrics.unserved_trips += len(self.pending)
            self.metrics.unserved_arrived_trips = self.metrics.unserved_trips
        else:
            self.clock.advance()
        self._refresh_derived_metrics()
        self.last_snapshot = self.snapshot(step_events)
        return self.last_snapshot

    def snapshot(self, step_events: list[dict[str, Any]]) -> dict[str, Any]:
        """Return the current serializable marketplace state."""
        imbalance = zone_demand_supply(self.pending, self.drivers)
        return {
            "time_min": self.clock.current_time_min,
            "decision_time_min": (
                self.clock.current_time_min - self.clock.step_min
                if step_events and not self.finished
                else self.clock.current_time_min
            ),
            "finished": self.finished,
            "pending_requests": [asdict(trip) for trip in self.pending],
            "drivers": [
                {
                    **asdict(driver),
                    "status": driver.status.value,
                    "movement": self._active_movements.get(driver.driver_id),
                    "location_model": "discrete endpoint",
                }
                for driver in self.drivers
            ],
            "events": step_events,
            "offers": [e for e in step_events if e["type"] in {"offer_accepted", "offer_rejected"}],
            "accepted_offers": [e for e in step_events if e["type"] == "offer_accepted"],
            "rejected_offers": [e for e in step_events if e["type"] == "offer_rejected"],
            "active_movements": list(self._active_movements.values()),
            "zone_state": {
                zone: {
                    **values,
                    "rider_premium_cad": self._last_adjustments.get(zone, (0.0, 0.0))[0],
                    "driver_bonus_cad": self._last_adjustments.get(zone, (0.0, 0.0))[1],
                }
                for zone, values in imbalance.items()
            },
            "metrics": asdict(self.metrics),
            "reposition_events": self.reposition_events,
            "routing_mode": self._routing_mode,
            "routing_fallback_reason": self._routing_fallback_reason,
            "matching_strategy": self.matching_strategy
            or (self.policy_settings.matching_strategy if self.policy_settings else "greedy"),
            "matching_backend": self._last_assignment_backend,
        }
