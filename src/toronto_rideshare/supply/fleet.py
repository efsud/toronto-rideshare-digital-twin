"""Initialize driver fleet across zones."""

from __future__ import annotations

import numpy as np

from toronto_rideshare.supply.models import Driver
from toronto_rideshare.zones import lat_lon_to_zone, zone_center


def initialize_fleet(
    zone_ids: list[str],
    *,
    fleet_size: int,
    random_seed: int = 42,
) -> list[Driver]:
    """Place drivers uniformly at random across given zones."""
    rng = np.random.default_rng(random_seed)
    drivers: list[Driver] = []
    if not zone_ids:
        return drivers

    for i in range(fleet_size):
        zone = str(rng.choice(zone_ids))
        lat, lon = zone_center(zone)
        lat += float(rng.normal(0, 0.001))
        lon += float(rng.normal(0, 0.001))
        drivers.append(
            Driver(
                driver_id=f"D{i:04d}",
                lat=lat,
                lon=lon,
                zone=lat_lon_to_zone(lat, lon),
            )
        )
    return drivers
