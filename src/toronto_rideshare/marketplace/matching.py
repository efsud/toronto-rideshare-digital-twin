"""Baseline greedy rider-driver matching."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import networkx as nx

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.marketplace.fares import FareBreakdown, compute_fare
from toronto_rideshare.network.routing import shortest_time_route
from toronto_rideshare.supply.models import Driver, DriverStatus

if TYPE_CHECKING:
    from toronto_rideshare.traffic.models import TrafficProfile


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def min_to_departure_time(minutes: float) -> str:
    """Convert simulation minutes-from-midnight to HH:MM departure bucket."""
    total = int(minutes) % (24 * 60)
    hour, minute = divmod(total, 60)
    return f"{hour:02d}:{minute:02d}"


@dataclass(frozen=True, slots=True)
class RoutingContext:
    """Optional OSM graph + traffic profile for network-based matching."""

    graph: nx.MultiDiGraph
    profile: TrafficProfile | None = None
    use_time_dependent: bool = True
    strict: bool = False
    _weighted: dict = field(default_factory=dict, compare=False, repr=False)
    _routes: dict = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class RouteEstimate:
    distance_km: float
    travel_time_min: float
    mode: str
    fallback_reason: str | None = None
    path: tuple = ()
    edge_keys: tuple = ()


@dataclass(frozen=True, slots=True)
class BatchAssignment:
    pairs: tuple[tuple[str, str, float], ...]
    strategy: str
    backend: str
    total_pickup_min: float
    fallback_reason: str | None = None


def estimate_route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    *,
    routing: RoutingContext | None,
    departure_time: str,
) -> RouteEstimate:
    """Route one leg and explicitly report network or fallback behavior."""
    cache_key = (origin, destination, departure_time)
    if routing is not None:
        if cache_key in routing._routes:
            return routing._routes[cache_key]
        try:
            if routing.profile is not None and routing.use_time_dependent:
                from toronto_rideshare.traffic.apply import (
                    apply_travel_times,
                    departure_time_to_bucket,
                )

                bucket = departure_time_to_bucket(
                    departure_time, routing.profile.time_buckets
                ).label
                if bucket not in routing._weighted:
                    routing._weighted[bucket] = apply_travel_times(
                        routing.graph, routing.profile, bucket
                    )
                result = shortest_time_route(
                    routing._weighted[bucket], origin, destination, weight="travel_time_t"
                )
                mode = "time-dependent network"
            else:
                result = shortest_time_route(routing.graph, origin, destination)
                mode = "network free-flow"
            estimate = RouteEstimate(
                result.distance_km,
                result.travel_time_min,
                mode,
                path=tuple(result.path),
                edge_keys=tuple(result.edge_keys),
            )
            if len(routing._routes) >= 4096:
                routing._routes.clear()
            routing._routes[cache_key] = estimate
            return estimate
        except (ValueError, KeyError, nx.NetworkXNoPath) as exc:
            fallback_reason = f"{type(exc).__name__}: {exc}"
            if routing.strict:
                raise nx.NetworkXNoPath(fallback_reason) from exc
    else:
        fallback_reason = "no routing context configured"

    dist_km = _haversine_km(origin[0], origin[1], destination[0], destination[1])
    speed_kph = 30.0 if dist_km < 5.0 else 25.0
    return RouteEstimate(
        dist_km,
        dist_km / speed_kph * 60.0,
        "haversine fallback",
        fallback_reason,
        path=((origin[1], origin[0]), (destination[1], destination[0])),
    )


def route_or_haversine(
    origin: tuple[float, float],
    destination: tuple[float, float],
    *,
    routing: RoutingContext | None,
    departure_time: str,
) -> tuple[float, float]:
    """Compatibility wrapper returning ``(distance_km, travel_time_min)``."""
    result = estimate_route(origin, destination, routing=routing, departure_time=departure_time)
    return result.distance_km, result.travel_time_min


def pickup_candidates(
    trip: TripRequest,
    drivers: list[Driver],
    current_time_min: float,
    *,
    routing: RoutingContext | None = None,
) -> list[tuple[float, Driver, RouteEstimate]]:
    """Return eligible drivers in deterministic pickup-cost order."""
    departure = min_to_departure_time(current_time_min)
    candidates = []
    for driver in drivers:
        if driver.status != DriverStatus.IDLE or driver.available_time_min > current_time_min:
            continue
        try:
            route = estimate_route(
                (driver.lat, driver.lon),
                (trip.origin_lat, trip.origin_lon),
                routing=routing,
                departure_time=departure,
            )
            if routing and routing.strict:
                estimate_route(
                    (trip.origin_lat, trip.origin_lon),
                    (trip.destination_lat, trip.destination_lon),
                    routing=routing,
                    departure_time=min_to_departure_time(current_time_min + route.travel_time_min),
                )
        except nx.NetworkXNoPath:
            continue
        candidates.append((route.travel_time_min, driver, route))
    return sorted(candidates, key=lambda item: (item[0], item[1].driver_id))


def batch_assign(
    pending_trips: list[TripRequest],
    drivers: list[Driver],
    current_time_min: float,
    *,
    routing: RoutingContext | None = None,
    use_ortools: bool = True,
) -> BatchAssignment:
    """Minimize total pickup time for one deterministic rider/driver batch."""
    trips = sorted(pending_trips, key=lambda trip: (trip.request_time_min, trip.request_id))
    available = sorted(
        (
            driver
            for driver in drivers
            if driver.status == DriverStatus.IDLE and driver.available_time_min <= current_time_min
        ),
        key=lambda driver: driver.driver_id,
    )
    if not trips or not available:
        return BatchAssignment((), "min_total_pickup", "none", 0.0)

    costs: dict[tuple[int, int], float] = {}
    for i, trip in enumerate(trips):
        eligible = {
            driver.driver_id: cost
            for cost, driver, _ in pickup_candidates(
                trip, available, current_time_min, routing=routing
            )
        }
        for j, driver in enumerate(available):
            if driver.driver_id in eligible:
                costs[i, j] = eligible[driver.driver_id]
    if not costs:
        return BatchAssignment((), "min_total_pickup", "none", 0.0, "No reachable assignments")

    if use_ortools:
        try:
            from ortools.linear_solver import pywraplp

            solver = pywraplp.Solver.CreateSolver("SCIP")
            if solver is None:
                raise RuntimeError("SCIP backend unavailable")
            variables = {(i, j): solver.BoolVar(f"x_{i}_{j}") for i, j in costs}
            for i in range(len(trips)):
                solver.Add(sum(variable for (r, _), variable in variables.items() if r == i) <= 1)
            for j in range(len(available)):
                solver.Add(sum(variable for (_, d), variable in variables.items() if d == j) <= 1)
            # Maximize feasible cardinality, then minimize pickup cost.
            penalty = (max(costs.values()) + 1) * (len(trips) + len(available))
            solver.Minimize(
                sum(
                    (round(costs[i, j], 9) - penalty + i * 1e-9 + j * 1e-12) * variable
                    for (i, j), variable in variables.items()
                )
            )
            if solver.Solve() != pywraplp.Solver.OPTIMAL:
                raise RuntimeError("assignment solver did not find an optimum")
            selected = [
                (i, j) for (i, j), variable in variables.items() if variable.solution_value() > 0.5
            ]
            backend = "ortools-scip"
            fallback_reason = None
        except (ImportError, RuntimeError) as exc:
            selected = []
            remaining = set(range(len(available)))
            for i in range(len(trips)):
                if not remaining:
                    break
                eligible = [j for j in remaining if (i, j) in costs]
                if not eligible:
                    continue
                j = min(eligible, key=lambda index: (costs[i, index], index))
                selected.append((i, j))
                remaining.remove(j)
            backend = "deterministic-greedy-fallback"
            fallback_reason = f"{type(exc).__name__}: {exc}"
    else:
        selected = []
        remaining = set(range(len(available)))
        for i in range(len(trips)):
            if not remaining:
                break
            eligible = [j for j in remaining if (i, j) in costs]
            if not eligible:
                continue
            j = min(eligible, key=lambda index: (costs[i, index], index))
            selected.append((i, j))
            remaining.remove(j)
        backend = "deterministic-greedy"
        fallback_reason = None

    pairs = tuple(
        (trips[i].request_id, available[j].driver_id, costs[i, j]) for i, j in sorted(selected)
    )
    return BatchAssignment(
        pairs,
        "min_total_pickup",
        backend,
        sum(pair[2] for pair in pairs),
        fallback_reason,
    )


def greedy_match(
    pending_trips: list[TripRequest],
    drivers: list[Driver],
    current_time_min: float,
    *,
    routing: RoutingContext | None = None,
    zone_adjustments: dict[str, tuple[float, float]] | None = None,
) -> list[tuple[TripRequest, Driver, float, float, FareBreakdown]]:
    """Match each pending trip to nearest available driver.

    When ``routing`` is provided, pickup and trip legs use OSM shortest-path
    travel times (time-dependent when a traffic profile is attached).
    Otherwise falls back to straight-line haversine proxies.
    """
    results: list[tuple[TripRequest, Driver, float, float, FareBreakdown]] = []
    available = [
        d
        for d in drivers
        if d.status == DriverStatus.IDLE and d.available_time_min <= current_time_min
    ]
    departure_time = min_to_departure_time(current_time_min)

    for trip in list(pending_trips):
        if not available:
            break

        candidates = pickup_candidates(trip, available, current_time_min, routing=routing)
        pickup_min, best_driver, _ = candidates[0]
        trip_route = estimate_route(
            (trip.origin_lat, trip.origin_lon),
            (trip.destination_lat, trip.destination_lon),
            routing=routing,
            departure_time=departure_time,
        )
        rider_adj, driver_bonus = (0.0, 0.0)
        if zone_adjustments and trip.origin_zone in zone_adjustments:
            rider_adj, driver_bonus = zone_adjustments[trip.origin_zone]

        fare = compute_fare(
            trip_route.distance_km,
            trip_route.travel_time_min,
            rider_adjustment_cad=rider_adj,
            driver_bonus_cad=driver_bonus,
        )
        best_driver.status = DriverStatus.WITH_RIDER
        best_driver.available_time_min = current_time_min + pickup_min + trip_route.travel_time_min
        best_driver.lat = trip.destination_lat
        best_driver.lon = trip.destination_lon
        best_driver.zone = trip.destination_zone
        available.remove(best_driver)
        results.append((trip, best_driver, pickup_min, trip_route.travel_time_min, fare))
    return results
