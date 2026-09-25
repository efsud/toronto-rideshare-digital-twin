import pytest

from toronto_rideshare.marketplace.decisions import (
    choose_request,
    driver_choice_probabilities,
    quote_trip,
    rider_quote_probability,
)


def test_incentive_reverses_with_destination_shortage():
    inbound = quote_trip("r", 480, 5, 15, -3, 5, adaptive=True)
    outbound = quote_trip("r", 1080, 5, 15, 5, -3, adaptive=True)
    assert inbound.fare.driver_bonus_cad > outbound.fare.driver_bonus_cad
    assert inbound.fare.rider_payment_cad < outbound.fare.rider_payment_cad
    assert inbound.transfer_value == -outbound.transfer_value
    assert rider_quote_probability(inbound) > rider_quote_probability(outbound)


def test_quote_budget_is_applied_before_acceptance_and_fares_stay_nonnegative():
    q = quote_trip("r", 0, 0, 0, -100, 100, adaptive=True, available_budget=2)
    assert q.fare.rider_payment_cad >= 0
    assert q.subsidy_cad == pytest.approx(2)
    no_budget = quote_trip("r", 0, 0, 0, -100, 100, adaptive=True, available_budget=0)
    assert no_budget.subsidy_cad == 0


def test_drivers_choose_between_prices_and_outside_option():
    offers = [("low", 10, 5, 10), ("high", 30, 5, 10)]
    p = driver_choice_probabilities(offers)
    assert p["high"] > p["low"] > 0
    assert p[None] > 0
    assert sum(p.values()) == pytest.approx(1)
    assert p == driver_choice_probabilities(list(reversed(offers)))
    counts = {key: 0 for key in p}
    for i in range(10000):
        counts[choose_request(p, i / 10000)] += 1
    for key in p:
        assert counts[key] / 10000 == pytest.approx(p[key], abs=0.0002)
    assert driver_choice_probabilities([]) == {None: 1.0}
