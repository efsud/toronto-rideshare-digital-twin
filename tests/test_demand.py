from toronto_rideshare.demand import generate_trips
from toronto_rideshare.zones import lat_lon_to_zone, zone_center


def test_generate_trips_count_and_zones() -> None:
    zone = lat_lon_to_zone(*zone_center(lat_lon_to_zone(43.65, -79.38)))
    trips = generate_trips([zone], n_trips=5, random_seed=1)
    assert len(trips) == 5
    assert trips == sorted(trips, key=lambda t: t.request_time_min)


def test_demand_multiplier_scales_count_not_arrival_window() -> None:
    zone = lat_lon_to_zone(43.65, -79.38)
    trips = generate_trips(
        [zone],
        n_trips=10,
        start_time_min=420.0,
        random_seed=1,
        demand_multiplier=1.5,
    )
    assert len(trips) == 15
    assert min(trip.request_time_min for trip in trips) >= 420.0
    assert max(trip.request_time_min for trip in trips) < 600.0
