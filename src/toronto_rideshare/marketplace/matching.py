"""Baseline greedy rider-driver matching."""

from __future__ import annotations

import math
from dataclasses import dataclass
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


def _route_or_haversine(
    origin: tuple[float, float],
    destination: tuple[float, float],
    *,
    routing: RoutingContext | None,
    departure_time: str,
) -> tuple[float, float]:
    """Return (distance_km, travel_time_min), falling back to haversine on failure."""
    if routing is not None:
        try:
            if routing.profile is not None and routing.use_time_dependent:
                from toronto_rideshare.traffic.apply import shortest_time_route_at

                result = shortest_time_route_at(
                    routing.graph,
                    origin,
                    destination,
                    routing.profile,
                    departure_time,
                )
            else:
                result = shortest_time_route(routing.graph, origin, destination)
            return result.distance_km, result.travel_time_min
        except (ValueError, KeyError, nx.NetworkXNoPath):
            pass

    dist_km = _haversine_km(origin[0], origin[1], destination[0], destination[1])
    speed_kph = 30.0 if dist_km < 5.0 else 25.0
    return dist_km, dist_km / speed_kph * 60.0


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

        def pickup_cost(d: Driver, t: TripRequest = trip) -> float:
            _, pickup_min = _route_or_haversine(
                (d.lat, d.lon),
                (t.origin_lat, t.origin_lon),
                routing=routing,
                departure_time=departure_time,
            )
            return pickup_min

        best_driver = min(available, key=pickup_cost)
        _, pickup_min = _route_or_haversine(
            (best_driver.lat, best_driver.lon),
            (trip.origin_lat, trip.origin_lon),
            routing=routing,
            departure_time=departure_time,
        )
        trip_km, trip_min = _route_or_haversine(
            (trip.origin_lat, trip.origin_lon),
            (trip.destination_lat, trip.destination_lon),
            routing=routing,
            departure_time=departure_time,
        )
        rider_adj, driver_bonus = (0.0, 0.0)
        if zone_adjustments and trip.origin_zone in zone_adjustments:
            rider_adj, driver_bonus = zone_adjustments[trip.origin_zone]

        fare = compute_fare(
            trip_km,
            trip_min,
            rider_adjustment_cad=rider_adj,
            driver_bonus_cad=driver_bonus,
        )
        best_driver.status = DriverStatus.WITH_RIDER
        best_driver.available_time_min = current_time_min + pickup_min + trip_min
        best_driver.lat = trip.destination_lat
        best_driver.lon = trip.destination_lon
        best_driver.zone = trip.destination_zone
        available.remove(best_driver)
        results.append((trip, best_driver, pickup_min, trip_min, fare))
    return results
