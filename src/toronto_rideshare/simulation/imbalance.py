"""Zone supply-demand imbalance metrics."""

from __future__ import annotations

from collections import Counter

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.supply.models import Driver, DriverStatus


def zone_demand_supply(
    trips: list[TripRequest],
    drivers: list[Driver],
) -> dict[str, dict[str, float]]:
    """Count demand (origins) and idle supply per zone."""
    demand = Counter(t.origin_zone for t in trips)
    supply = Counter(d.zone for d in drivers if d.status == DriverStatus.IDLE)
    zones = set(demand) | set(supply)
    return {
        z: {
            "demand": float(demand.get(z, 0)),
            "supply": float(supply.get(z, 0)),
            "imbalance": float(demand.get(z, 0)) - float(supply.get(z, 0)),
        }
        for z in zones
    }
