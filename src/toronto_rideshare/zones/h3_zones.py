"""H3 hexagonal zoning for Toronto marketplace spatial aggregation."""

from __future__ import annotations

import h3

DEFAULT_RESOLUTION = 8

TORONTO_BBOX = {
    "min_lat": 43.58,
    "max_lat": 43.86,
    "min_lon": -79.64,
    "max_lon": -79.12,
}


def lat_lon_to_zone(lat: float, lon: float, resolution: int = DEFAULT_RESOLUTION) -> str:
    """Return H3 cell id for a latitude/longitude point."""
    return h3.latlng_to_cell(lat, lon, resolution)


def zone_center(cell: str) -> tuple[float, float]:
    """Return (lat, lon) center of an H3 cell."""
    lat, lon = h3.cell_to_latlng(cell)
    return lat, lon


def toronto_zone_cells(resolution: int = DEFAULT_RESOLUTION) -> set[str]:
    """Approximate Toronto coverage as a set of H3 cells over the bounding box."""
    cells: set[str] = set()
    lat = TORONTO_BBOX["min_lat"]
    while lat <= TORONTO_BBOX["max_lat"]:
        lon = TORONTO_BBOX["min_lon"]
        while lon <= TORONTO_BBOX["max_lon"]:
            cells.add(lat_lon_to_zone(lat, lon, resolution))
            lon += 0.02
        lat += 0.02
    return cells
