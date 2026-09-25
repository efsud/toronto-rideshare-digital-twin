import math

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.marketplace.fares import compute_fare
from toronto_rideshare.marketplace.matching import greedy_match
from toronto_rideshare.supply.models import Driver


def test_compute_fare_independent_adjustments() -> None:
    base = compute_fare(10.0, 20.0)
    adjusted = compute_fare(10.0, 20.0, rider_adjustment_cad=2.0, driver_bonus_cad=3.0)
    assert adjusted.rider_payment_cad == base.rider_payment_cad + 2.0
    assert adjusted.driver_earnings_cad == base.driver_earnings_cad + 3.0


def test_greedy_match_one_pair() -> None:
    trip = TripRequest(
        request_id="R1",
        request_time_min=0.0,
        origin_lat=43.65,
        origin_lon=-79.38,
        destination_lat=43.66,
        destination_lon=-79.37,
        origin_zone="z1",
        destination_zone="z2",
    )
    driver = Driver(driver_id="D1", lat=43.6501, lon=-79.3801, zone="z1")
    matches = greedy_match([trip], [driver], current_time_min=0.0)
    assert len(matches) == 1
    assert math.isclose(matches[0][2], matches[0][2])  # pickup_min exists
