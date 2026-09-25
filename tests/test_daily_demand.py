"""Evidence for daily demand reversals and policy-independent request generation."""

from toronto_rideshare.demand import generate_trips
from toronto_rideshare.demand.profiles import region_for_zone
from toronto_rideshare.experiments.runner import create_engine
from toronto_rideshare.scenario import ScenarioConfig, time_minutes
from toronto_rideshare.zones import toronto_zone_cells


def test_full_day_interval_and_endpoints():
    assert time_minutes("24:00") == 1440
    engine = create_engine(
        {
            "simulation": {
                "start_time": "00:00",
                "end_time": "24:00",
                "fleet_size": 0,
                "base_trip_count": 100,
                "demand_profile": "synthetic_daily",
            }
        }
    )
    engine.run()
    assert engine.last_snapshot["processed_time_min"] == 1440
    assert engine.last_snapshot["metrics"]["not_yet_released_trips"] == 0
    assert min(t.request_time_min for t in engine.trips) >= 0
    assert max(t.request_time_min for t in engine.trips) < 1440


def test_daily_od_reverses_and_peak_arrivals_exceed_overnight():
    trips = generate_trips(
        list(toronto_zone_cells()),
        n_trips=3000,
        end_time_min=1440,
        demand_profile="synthetic_daily",
    )
    morning = [t for t in trips if 360 <= t.request_time_min < 600]
    evening = [t for t in trips if 960 <= t.request_time_min < 1200]
    overnight = [t for t in trips if t.request_time_min < 360]
    assert len(morning) / 4 > 3 * len(overnight) / 6
    assert (
        sum(region_for_zone(t.destination_zone) == "central" for t in morning) > len(morning) * 0.7
    )
    assert sum(region_for_zone(t.origin_zone) == "central" for t in evening) > len(evening) * 0.7
    assert sum(region_for_zone(t.origin_zone) == "central" for t in morning) < len(morning) * 0.2


def test_request_probability_thins_same_potential_population():
    args = dict(
        zone_ids=list(toronto_zone_cells()),
        n_trips=100,
        end_time_min=1440,
        demand_profile="synthetic_daily",
        random_seed=3,
    )
    full = {t.request_id: t for t in generate_trips(**args)}
    thinned = generate_trips(**args, request_probability=0.5)
    assert 25 < len(thinned) < 75
    assert all(full[t.request_id] == t for t in thinned)
    assert generate_trips(**args, request_probability=0) == []


def test_daily_policy_inputs_are_identical():
    config = ScenarioConfig.from_source("configs/experiments/full_day.yaml").as_dict()
    config["simulation"]["base_trip_count"] = 30
    baseline = create_engine(config)
    reposition = create_engine(config, policy_id="P5_repositioning")
    assert baseline.trips == reposition.trips
    assert baseline.drivers == reposition.drivers
