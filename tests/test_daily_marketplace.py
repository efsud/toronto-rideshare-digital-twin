from dataclasses import asdict

import pytest

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.experiments.runner import create_engine
from toronto_rideshare.policies.registry import ACTIVE_POLICIES, POLICY_REGISTRY, PolicyId
from toronto_rideshare.simulation import SimulationClock, SimulationEngine
from toronto_rideshare.simulation.daily_marketplace import committed_subsidy
from toronto_rideshare.supply.models import Driver
from toronto_rideshare.zones import lat_lon_to_zone


def small_engine(policy=PolicyId.ADAPTIVE, fleet=1):
    a, b = (43.65, -79.38), (43.67, -79.40)
    za, zb = lat_lon_to_zone(*a), lat_lon_to_zone(*b)
    return SimulationEngine(
        SimulationClock(0, 60, 5),
        [Driver(f"D{i}", *a, za) for i in range(fleet)],
        [TripRequest(f"R{i}", 0, *a, *b, za, zb) for i in range(3)],
        policy_settings=POLICY_REGISTRY[policy],
        marketplace_model="driver_choice",
        behavior_profile="shared",
        daily_behavior={"rider_intercept": 40},
        policy_cfg={"subsidy_budget_cad": 2},
        max_wait_time_min=15,
    )


def test_rider_quote_precedes_competing_driver_menu_and_is_honored():
    e = small_engine()
    while not e.finished:
        e.step()
        assert e.metrics.subsidy_spend_cad + committed_subsidy(e) <= 2 + 1e-9
    proposed = {
        x["request_id"]: x["quote"]["fare"] for x in e.events if x["type"] == "price_proposed"
    }
    accepted = [x for x in e.events if x["type"] == "offer_accepted"]
    menus = [x for x in e.events if x["type"] == "driver_choice"]
    assert any(len(x["menu"]) >= 2 for x in menus)
    assert len(proposed) == 3
    assert accepted
    assert len({x["request_id"] for x in accepted}) == len(accepted)
    for x in accepted:
        assert x["rider_payment_cad"] == proposed[x["request_id"]]["rider_payment_cad"]
        assert x["driver_earnings_cad"] == proposed[x["request_id"]]["driver_earnings_cad"]
        proposal_index = next(
            i
            for i, item in enumerate(e.events)
            if item["type"] == "price_proposed" and item["request_id"] == x["request_id"]
        )
        assert proposal_index < e.events.index(x)
    m = e.metrics
    assert m.completed_trips + m.in_progress_trips + m.unserved_trips == 3
    assert m.total_rider_payment_cad - m.total_driver_earnings_cad == pytest.approx(
        m.platform_net_revenue_cad
    )


def test_unassigned_quote_reservations_release_on_cancellation():
    e = small_engine(fleet=0)
    e.step()
    assert len(e.quotes) == 3
    e.run()
    assert not e.quotes
    assert committed_subsidy(e) == 0
    assert e.metrics.cancelled_trips == 3


def test_three_policies_have_identical_requests_fleet_and_behavior():
    engines = [
        create_engine("configs/experiments/full_day.yaml", policy_id=p) for p in ACTIVE_POLICIES
    ]
    reference = engines[0]
    assert len(engines) == 3
    for e in engines:
        assert e.trips == reference.trips
        assert [asdict(d) for d in e.drivers] == [asdict(d) for d in reference.drivers]
        assert e.daily_behavior == reference.daily_behavior
        assert e.acceptance == reference.acceptance
        assert e._draw("rider_quote", "R42") == reference._draw("rider_quote", "R42")
        assert e._draw("driver_choice", 60, "D1") == reference._draw("driver_choice", 60, "D1")


def test_idle_choice_has_truthful_driver_location_overlay():
    e = small_engine()
    e._draw = lambda kind, *args: 0.0 if kind == "driver_choice" else 0.5
    snapshot = e.step()
    rejections = snapshot["rejected_offers"]
    assert rejections
    assert rejections[0]["decision_scope"] == "menu"
    assert rejections[0]["location_kind"] == "driver_location"
    assert rejections[0]["origin"] == [e.drivers[0].lat, e.drivers[0].lon]
    assert not snapshot["accepted_offers"]


def test_default_config_matches_daily_workspace():
    from toronto_rideshare.scenario import ScenarioConfig

    assert (
        ScenarioConfig.from_source({}).as_dict()
        == ScenarioConfig.from_source("configs/experiments/full_day.yaml").as_dict()
    )
