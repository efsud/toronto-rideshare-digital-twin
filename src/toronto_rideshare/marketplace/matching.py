"""Baseline greedy rider-driver matching."""

from __future__ import annotations

import math

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.marketplace.fares import FareBreakdown, compute_fare
from toronto_rideshare.supply.models import Driver, DriverStatus


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def greedy_match(
    pending_trips: list[TripRequest],
    drivers: list[Driver],
    current_time_min: float,
) -> list[tuple[TripRequest, Driver, float, float, FareBreakdown]]:
    """Match each pending trip to nearest available driver (straight-line proxy)."""
    results: list[tuple[TripRequest, Driver, float, float, FareBreakdown]] = []
    available = [
        d
        for d in drivers
        if d.status == DriverStatus.IDLE and d.available_time_min <= current_time_min
    ]

    for trip in list(pending_trips):
        if not available:
            break
        best_driver = min(
            available,
            key=lambda d: _haversine_km(d.lat, d.lon, trip.origin_lat, trip.origin_lon),
        )
        pickup_km = _haversine_km(
            best_driver.lat, best_driver.lon, trip.origin_lat, trip.origin_lon
        )
        trip_km = _haversine_km(
            trip.origin_lat, trip.origin_lon, trip.destination_lat, trip.destination_lon
        )
        pickup_min = pickup_km / 30.0 * 60.0  # 30 km/h proxy
        trip_min = trip_km / 25.0 * 60.0
        fare = compute_fare(trip_km, trip_min)
        best_driver.status = DriverStatus.WITH_RIDER
        best_driver.available_time_min = current_time_min + pickup_min + trip_min
        best_driver.lat = trip.destination_lat
        best_driver.lon = trip.destination_lon
        best_driver.zone = trip.destination_zone
        available.remove(best_driver)
        results.append((trip, best_driver, pickup_min, trip_min, fare))
    return results
