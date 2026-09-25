"""Seeded potential requests from explicit synthetic demand assumptions."""

from __future__ import annotations

import numpy as np

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.demand.profiles import (
    location_weights,
    region_for_zone,
    sample_arrival,
)
from toronto_rideshare.zones import lat_lon_to_zone
from toronto_rideshare.zones.sampling import sample_location


def generate_trips(
    zone_ids: list[str],
    *,
    n_trips: int,
    start_time_min: float = 0.0,
    random_seed: int = 42,
    end_time_min: float | None = None,
    demand_multiplier: float = 1.0,
    demand_profile: str = "uniform",
    request_probability: float = 1.0,
) -> list[TripRequest]:
    """Generate demand; multiplier scales count, never the arrival window."""
    rng = np.random.default_rng(random_seed)
    trips: list[TripRequest] = []
    if not zone_ids:
        return trips

    if demand_profile not in ("uniform", "synthetic_daily"):
        raise ValueError("Unknown demand profile")
    if not 0 <= request_probability <= 1:
        raise ValueError("Request probability must be in [0,1]")
    end = start_time_min + 180 if end_time_min is None else end_time_min
    if end < start_time_min:
        raise ValueError("Demand end time precedes start")
    regions = [region_for_zone(z) for z in zone_ids] if demand_profile != "uniform" else []
    # Independent thinning does not shift subsequent potential arrivals or locations.
    request_rng = np.random.default_rng(np.random.SeedSequence([random_seed, 1]))
    scaled_count = max(0, int(round(n_trips * demand_multiplier)))
    for i in range(scaled_count):
        t_min = sample_arrival(rng, start_time_min, end, demand_profile)
        origin_weights = location_weights(regions, t_min) if regions else None
        destination_weights = (
            location_weights(regions, t_min, destination=True) if regions else None
        )
        origin_zone = str(rng.choice(zone_ids, p=origin_weights))
        dest_zone = str(rng.choice(zone_ids, p=destination_weights))
        o_lat, o_lon = sample_location(origin_zone, rng)
        d_lat, d_lon = sample_location(dest_zone, rng)
        if request_rng.random() >= request_probability:
            continue
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
