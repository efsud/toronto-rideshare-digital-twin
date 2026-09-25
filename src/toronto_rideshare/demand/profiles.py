"""Explicit synthetic daily regimes; not inferred Toronto travel patterns."""

from functools import lru_cache

import numpy as np

from toronto_rideshare.zones import zone_center

REGIONS = ("central", "west", "east", "north")
# Hour bands: relative arrivals and region shares for origins / destinations.
REGIMES = (
    (0, 6, "overnight", 0.25, (6, 1, 1, 1), (2, 2, 2, 2)),
    (6, 10, "morning inbound", 2.0, (1, 3, 3, 3), (12, 1, 1, 1)),
    (10, 16, "midday distributed", 1.0, (4, 2, 2, 2), (4, 2, 2, 2)),
    (16, 20, "evening outbound", 2.2, (12, 1, 1, 1), (1, 3, 3, 3)),
    (20, 24, "night activity", 0.8, (3, 2, 2, 1), (8, 1, 1, 1)),
)


def region_for_location(lat, lon):
    if lat < 43.69 and -79.44 <= lon <= -79.33:
        return "central"
    if lat >= 43.75:
        return "north"
    return "west" if lon < -79.40 else "east"


@lru_cache(maxsize=8192)
def region_for_zone(zone):
    return region_for_location(*zone_center(zone))


def regime_at(minutes):
    hour = (minutes % 1440) / 60
    return next(row for row in REGIMES if row[0] <= hour < row[1])


def sample_arrival(rng, start, end, profile):
    if profile == "uniform" or start == end:
        return float(rng.uniform(start, end))
    # Intersect hourly intervals with the requested window, preserving partial hours.
    intervals = [
        (max(start, h), min(end, h + 60))
        for h in range(int(start // 60) * 60, int(np.ceil(end / 60)) * 60, 60)
    ]
    weights = np.array([(b - a) * regime_at(a)[3] for a, b in intervals])
    a, b = intervals[int(rng.choice(len(intervals), p=weights / weights.sum()))]
    return float(rng.uniform(a, b))


def location_weights(regions, minutes, *, destination=False):
    """Region shares are independent of the number of cells/nodes in each region."""
    shares = regime_at(minutes)[5 if destination else 4]
    counts = {r: regions.count(r) for r in REGIONS}
    weights = np.array([shares[REGIONS.index(r)] / counts[r] for r in regions])
    return weights / weights.sum()
