from toronto_rideshare.zones import lat_lon_to_zone, zone_center


def test_lat_lon_to_zone_roundtrip_center() -> None:
    lat, lon = 43.6532, -79.3832
    cell = lat_lon_to_zone(lat, lon)
    c_lat, c_lon = zone_center(cell)
    assert abs(c_lat - lat) < 0.05
    assert abs(c_lon - lon) < 0.05
