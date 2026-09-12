from toronto_rideshare.demand import generate_trips
from toronto_rideshare.zones import lat_lon_to_zone, zone_center


def test_generate_trips_count_and_zones() -> None:
    zone = lat_lon_to_zone(*zone_center(lat_lon_to_zone(43.65, -79.38)))
    trips = generate_trips([zone], n_trips=5, random_seed=1)
    assert len(trips) == 5
    assert trips == sorted(trips, key=lambda t: t.request_time_min)
