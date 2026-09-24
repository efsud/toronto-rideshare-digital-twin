"""Boundary-constrained synthetic agent placement."""

from functools import lru_cache

from shapely.geometry import Point, Polygon

from toronto_rideshare.zones.h3_zones import toronto_boundary, zone_boundary


@lru_cache(maxsize=4096)
def clipped_zone(cell):
    polygon = Polygon([(lon, lat) for lat, lon in zone_boundary(cell)])
    return polygon.intersection(toronto_boundary())


def sample_location(cell, rng):
    polygon = clipped_zone(cell)
    if polygon.is_empty:
        raise ValueError(f"Zone {cell} does not intersect the Toronto study area")
    west, south, east, north = polygon.bounds
    for _ in range(1000):
        lon, lat = rng.uniform(west, east), rng.uniform(south, north)
        if polygon.covers(Point(lon, lat)):
            return float(lat), float(lon)
    point = polygon.representative_point()
    return float(point.y), float(point.x)
