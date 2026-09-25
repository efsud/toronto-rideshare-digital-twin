from toronto_rideshare.zones import (
    lat_lon_to_zone,
    point_is_in_toronto,
    toronto_zone_cells,
    zone_boundary,
    zone_center,
)


def test_lat_lon_to_zone_roundtrip_center() -> None:
    lat, lon = 43.6532, -79.3832
    cell = lat_lon_to_zone(lat, lon)
    c_lat, c_lon = zone_center(cell)
    assert abs(c_lat - lat) < 0.05
    assert abs(c_lon - lon) < 0.05


def test_toronto_polyfill_is_land_only_and_deterministic() -> None:
    first = toronto_zone_cells()
    second = toronto_zone_cells()
    assert first == second
    assert first == tuple(sorted(first))
    assert len(first) > 100
    assert all(point_is_in_toronto(*zone_center(cell)) for cell in first)
    assert point_is_in_toronto(43.6532, -79.3832)
    assert not point_is_in_toronto(43.6000, -79.3500)  # Lake Ontario
    assert not point_is_in_toronto(43.7500, -79.6500)  # Peel Region
    assert not point_is_in_toronto(43.8000, -79.1000)  # Durham Region


def test_zone_boundary_is_closed() -> None:
    ring = zone_boundary(toronto_zone_cells()[0])
    assert len(ring) == 7
    assert ring[0] == ring[-1]
