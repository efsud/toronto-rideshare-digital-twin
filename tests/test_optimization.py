from toronto_rideshare.optimization.pricing_opt import optimize_zone_pricing


def test_optimize_zone_pricing_respects_caps() -> None:
    imbalance = {
        "z1": {"demand": 10.0, "supply": 2.0, "imbalance": 8.0},
        "z2": {"demand": 1.0, "supply": 5.0, "imbalance": -4.0},
    }
    decisions = optimize_zone_pricing(imbalance, rider_cap=5.0, bonus_cap=12.0)
    assert len(decisions) == 2
    for d in decisions:
        assert -5.0 <= d.rider_adjustment_cad <= 5.0
        assert 0.0 <= d.driver_bonus_cad <= 12.0


def test_optimize_zone_pricing_empty() -> None:
    assert optimize_zone_pricing({}) == []
