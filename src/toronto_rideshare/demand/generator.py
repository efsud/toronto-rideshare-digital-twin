"""Synthetic rider demand generator calibrated to zone-level rates."""

from __future__ import annotations

import numpy as np

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.zones import lat_lon_to_zone, zone_center


def generate_trips(
    zone_ids: list[str],
    *,
    n_trips: int,
    start_time_min: float = 0.0,
    random_seed: int = 42,
    demand_multiplier: float = 1.0,
) -> list[TripRequest]:
    """Generate synthetic OD trips between random zone pairs."""
    rng = np.random.default_rng(random_seed)
    trips: list[TripRequest] = []
    if not zone_ids:
        return trips

    for i in range(n_trips):
        origin_zone = str(rng.choice(zone_ids))
        dest_zone = str(rng.choice(zone_ids))
        o_lat, o_lon = zone_center(origin_zone)
        d_lat, d_lon = zone_center(dest_zone)
        # jitter within cell
        o_lat += float(rng.normal(0, 0.001))
        o_lon += float(rng.normal(0, 0.001))
        d_lat += float(rng.normal(0, 0.001))
        d_lon += float(rng.normal(0, 0.001))
        t_min = start_time_min + float(rng.uniform(0, 180)) * demand_multiplier
        trips.append(
            TripRequest(
                request_id=f"R{i:05d}",
                request_time_min=t_min,
                origin_lat=o_lat,
                origin_lon=o_lon,
                destination_lat=d_lat,
                destination_lon=d_lon,
                origin_zone=lat_lon_to_zone(o_lat, o_lon),
                destination_zone=lat_lon_to_zone(d_lat, d_lon),
            )
        )
    trips.sort(key=lambda t: t.request_time_min)
    return trips
