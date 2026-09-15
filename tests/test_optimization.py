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


def test_pricing_lp_budget_fairness_and_actual_ortools_path() -> None:
    imbalance = {
        "high": {"demand": 20.0, "supply": 1.0, "imbalance": 19.0},
        "low": {"demand": 2.0, "supply": 20.0, "imbalance": -18.0},
    }
    decisions = optimize_zone_pricing(
        imbalance,
        total_budget_cad=25.0,
        fairness_bound_cad=2.0,
    )
    assert {decision.backend for decision in decisions} == {"ortools-glop"}
    assert sum(decision.expected_subsidy_cad for decision in decisions) <= 25.0 + 1e-6
    assert (
        max(decision.rider_adjustment_cad for decision in decisions)
        - min(decision.rider_adjustment_cad for decision in decisions)
        <= 2.0 + 1e-6
    )
    assert (
        max(decision.driver_bonus_cad for decision in decisions)
        - min(decision.driver_bonus_cad for decision in decisions)
        <= 2.0 + 1e-6
    )
    assert all(decision.expected_subsidy_cad >= 0.0 for decision in decisions)
