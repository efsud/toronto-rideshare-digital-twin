"""H3 zoning clipped to an official-data-derived Toronto land boundary."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import h3
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry

DEFAULT_RESOLUTION = 8

BOUNDARY_PATH = Path(__file__).parent / "data" / "toronto_boundary.geojson"


def lat_lon_to_zone(lat: float, lon: float, resolution: int = DEFAULT_RESOLUTION) -> str:
    """Return H3 cell id for a latitude/longitude point."""
    return h3.latlng_to_cell(lat, lon, resolution)


def zone_center(cell: str) -> tuple[float, float]:
    """Return (lat, lon) center of an H3 cell."""
    lat, lon = h3.cell_to_latlng(cell)
    return lat, lon


@lru_cache(maxsize=1)
def toronto_boundary_geojson() -> dict[str, Any]:
    """Load the persisted City of Toronto Open Data ward-union boundary."""
    return json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def toronto_boundary() -> BaseGeometry:
    """Return the Toronto land polygon used for zoning."""
    return shape(toronto_boundary_geojson()["features"][0]["geometry"])


def point_is_in_toronto(lat: float, lon: float) -> bool:
    """Return whether a WGS84 point is covered by the zoning polygon."""
    return bool(toronto_boundary().covers(Point(lon, lat)))


@lru_cache(maxsize=8)
def toronto_zone_cells(resolution: int = DEFAULT_RESOLUTION) -> tuple[str, ...]:
    """Return deterministic H3 cells whose centers lie inside Toronto.

    H3's polygon fill uses cell-center containment. This avoids the former
    rectangular sampling that admitted Lake Ontario and adjacent municipalities.
    """
    geometry = toronto_boundary_geojson()["features"][0]["geometry"]
    rings = geometry["coordinates"]
    if geometry["type"] != "Polygon":
        raise ValueError("Toronto boundary asset must contain one Polygon")
    outer = [(lat, lon) for lon, lat in rings[0]]
    holes = [[(lat, lon) for lon, lat in ring] for ring in rings[1:]]
    cells = h3.polygon_to_cells(h3.LatLngPoly(outer, *holes), resolution)
    return tuple(sorted(cells))


def zone_boundary(cell: str) -> list[tuple[float, float]]:
    """Return a closed ``[(lat, lon), ...]`` H3 boundary ring."""
    ring = list(h3.cell_to_boundary(cell))
    return [*ring, ring[0]]


def zone_feature(cell: str) -> dict[str, Any]:
    """Return a GeoJSON polygon feature with center coordinates."""
    lat, lon = zone_center(cell)
    ring = [[point_lon, point_lat] for point_lat, point_lon in zone_boundary(cell)]
    return {
        "type": "Feature",
        "properties": {"zone": cell, "lat": lat, "lon": lon},
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }
