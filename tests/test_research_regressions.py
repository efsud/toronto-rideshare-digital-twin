"""Behavior-level regressions for the independent audit and research contract."""

import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import networkx as nx
import pandas as pd
import pytest
from shapely.geometry import shape

from toronto_rideshare.demand import generate_trips
from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.experiments.runner import (
    create_engine,
    run_experiment,
    run_repeated_policy_comparison,
)
from toronto_rideshare.marketplace.fares import compute_fare
from toronto_rideshare.marketplace.matching import RoutingContext, batch_assign, estimate_route
from toronto_rideshare.policies.behavior import OfferAcceptanceConfig
from toronto_rideshare.presentation import movement_paths, zone_features
from toronto_rideshare.scenario import ScenarioConfig
from toronto_rideshare.simulation import SimulationClock, SimulationEngine
from toronto_rideshare.supply.models import Driver
from toronto_rideshare.traffic import (
    build_traffic_profile_from_file,
    load_traffic_profile,
    save_traffic_profile,
)
from toronto_rideshare.traffic.ingest import clean_observations, load_traffic_observations
from toronto_rideshare.traffic.public_data import heldout_sites, normalize_speed_bins
from toronto_rideshare.validation import DatasetProvenance, validate_aggregate_metrics
from toronto_rideshare.zones import point_is_in_toronto, toronto_boundary, toronto_zone_cells

ACCEPT = OfferAcceptanceConfig(40, 0, 0)


def trip(name, at=0, lon=-79.38, dest=-79.38):
    return TripRequest(name, at, 43.65, lon, 43.65, dest, "z", "z")


def graph():
    g = nx.MultiDiGraph(crs="epsg:4326")
    g.add_node(1, x=-79.3839, y=43.6535)
    g.add_node(2, x=-79.38, y=43.6535)
    g.add_edge(1, 2, 0, length=300, travel_time=30, speed_kph=36, highway="primary")
    return g


def test_supplied_csv_to_profile_roundtrip(tmp_path):
    path = "data/synthetic/traffic_observations_sample.csv"
    frame = clean_observations(load_traffic_observations(path))
    assert len(frame) == 12
    assert str(frame.datetime.dt.tz) == "America/Toronto"
    profile, mapping = build_traffic_profile_from_file(graph(), path)
    assert len(mapping) >= 1
    saved = save_traffic_profile(profile, tmp_path / "profile.parquet")
    restored = load_traffic_profile(saved)
    assert len(restored.edge_stats) == 4
    assert (restored.edge_stats.travel_time_s > 0).all()
    assert "cost_source" in restored.edge_stats


def test_graph_roundtrip(tmp_path):
    from toronto_rideshare.network import load_graph, save_graph

    path = save_graph(graph(), tmp_path / "graph.graphml")
    restored = load_graph(path)
    assert restored.edges[1, 2, 0]["length"] == 300


def test_empty_comparison_is_not_validation(tmp_path):
    evidence = tmp_path / "evidence.csv"
    evidence.write_text("metric,value\nwait,5\n")
    p = DatasetProvenance("test", "https://example.com", "2026-09-24", "test", str(evidence))
    assert validate_aggregate_metrics({"wait": 5}, {}, provenance=p).status == "insufficient_data"
    assert (
        validate_aggregate_metrics({"wait": float("nan")}, {"wait": 5}, provenance=p).status
        == "insufficient_data"
    )
    assert (
        validate_aggregate_metrics({"wait": 5}, {"wait": 4}, provenance=p).status
        == "compared_with_observed"
    )


def test_optimizer_reservation_reaches_engine():
    trips = [trip("R1", lon=-79.5), trip("R2")]
    drivers = [Driver("D1", 43.65, -79.38, "z")]
    assignment = batch_assign(trips, drivers, 0)
    engine = SimulationEngine(
        SimulationClock(end_time_min=0),
        drivers,
        trips,
        matching_strategy="optimal_batch",
        acceptance=ACCEPT,
    )
    engine.run()
    actual = [
        (e["request_id"], e["driver_id"]) for e in engine.events if e["type"] == "offer_accepted"
    ]
    assert actual == [(r, d) for r, d, _ in assignment.pairs] == [("R2", "D1")]


def test_non_aligned_horizon():
    engine = SimulationEngine(SimulationClock(end_time_min=7, step_min=5), [], [trip("future", 9)])
    engine.run()
    assert engine.clock.current_time_min == 7
    assert engine.metrics.not_yet_released_trips == 1
    assert not engine.events


def test_end_assignment_does_not_count_future_utilization():
    engine = SimulationEngine(
        SimulationClock(end_time_min=60),
        [Driver("D1", 43.65, -79.38, "z")],
        [trip("R1", 60, dest=-79.5)],
        acceptance=ACCEPT,
    )
    engine.run()
    assert engine.metrics.utilization_rate == 0
    assert engine.metrics.in_progress_trips == 1


def test_partial_movement_utilization_is_actual_elapsed():
    engine = SimulationEngine(
        SimulationClock(end_time_min=7, step_min=5),
        [Driver("D1", 43.65, -79.38, "z")],
        [trip("R1", 0, dest=-79.5)],
        acceptance=ACCEPT,
    )
    engine.run()
    assert engine.metrics.elapsed_busy_min == 7
    assert engine.metrics.utilization_rate == 1


def test_boundary_sampling_and_window():
    trips = generate_trips(
        list(toronto_zone_cells()), n_trips=1000, start_time_min=10, end_time_min=17, random_seed=42
    )
    assert all(10 <= t.request_time_min <= 17 for t in trips)
    assert all(
        point_is_in_toronto(t.origin_lat, t.origin_lon)
        and point_is_in_toronto(t.destination_lat, t.destination_lon)
        for t in trips
    )


def test_clipped_map_and_actual_active_leg():
    engine = SimulationEngine(
        SimulationClock(end_time_min=60),
        [Driver("D1", 43.65, -79.38, "z")],
        [trip("R1", lon=-79.5, dest=-79.6)],
        acceptance=ACCEPT,
    )
    snapshot = engine.step()
    paths = movement_paths(snapshot)
    assert paths[0]["path"][0] == [-79.38, 43.65]
    assert "illustrative" in paths[0]["tooltip"]
    features, _ = zone_features(snapshot, "Shortage")
    assert all(shape(f["geometry"]).difference(toronto_boundary()).area < 1e-12 for f in features)


def test_route_geometry_and_strict_no_path():
    g = graph()
    ctx = RoutingContext(g, strict=True)
    route = estimate_route(
        (43.6535, -79.3839), (43.6535, -79.38), routing=ctx, departure_time="07:00"
    )
    assert route.edge_keys == ((1, 2, 0),)
    assert route.path[0] == [-79.3839, 43.6535]
    with pytest.raises(nx.NetworkXNoPath):
        estimate_route((43.6535, -79.38), (43.6535, -79.3839), routing=ctx, departure_time="07:00")


def test_fares_never_pay_rider_for_trip():
    fare = compute_fare(0, 0, rider_adjustment_cad=-5)
    assert fare.rider_payment_cad == 0
    assert fare.rider_adjustment_cad == -3.5


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("simulation", "decision_interval_minutes", 0),
        ("simulation", "fleet_size", -1),
        ("simulation", "demand_multiplier", float("nan")),
        ("policy", "reposition_acceptance", 1.1),
        ("simulation", "end_time", "04:00"),
        ("policy", "subsidy_budget_cad", -1),
    ],
)
def test_bad_scenario_rejected(section, key, value):
    config = ScenarioConfig.from_source({}).as_dict()
    config[section][key] = value
    with pytest.raises(ValueError):
        ScenarioConfig.from_source(config)


def test_ui_factory_and_cli_have_identical_inputs_and_metrics():
    config = ScenarioConfig.from_source({})
    engine = create_engine(config)
    actual = asdict(engine.run())
    result = run_experiment(config)
    assert actual == result["metrics"]
    assert result["manifest"]["scenario"] == config.as_dict()
    assert result["manifest"]["schema_version"] == 2


def test_shared_behavior_and_event_draws():
    from toronto_rideshare.policies.registry import PolicyId

    engines = [create_engine({}, policy_id=p) for p in PolicyId]
    assert all(e.behavior == engines[0].behavior for e in engines)
    assert engines[0]._draw("offer", "R1", "D1", 420) == engines[-1]._draw("offer", "R1", "D1", 420)
    assert engines[0].trips == engines[-1].trips
    assert not engines[0].additional_bonus_response


def test_single_seed_uncertainty_and_explicit_p0():
    from toronto_rideshare.policies.registry import PolicyId

    result = run_repeated_policy_comparison({}, policies=(PolicyId.P1,), n_replicates=1)
    assert result["reference_policy"] == PolicyId.P0
    assert len(result["replicates"]) == 2
    assert result["aggregates"][0]["metrics"]["service_rate"]["ci95_low"] is None
    assert result["aggregates"][0]["paired_delta_vs_p0"]["service_rate"]["mean"] == 0


def test_concurrent_engines_are_independent():
    engines = [create_engine({}) for _ in range(2)]
    original = copy.deepcopy(engines[1].drivers)
    engines[0].step()
    assert engines[1].drivers == original
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda e: asdict(e.run()), engines))
    assert results[0] == results[1]


def test_public_speed_bins_and_site_holdout():
    raw = pd.DataFrame(
        [
            {
                "id": i,
                "count_id": i,
                "centreline_id": i // 2,
                "time_start": "2025-01-01 08:00",
                "direction": "EB",
                "latitude": 43.65,
                "longitude": -79.38,
                "vol_20_25kph": 2,
                "vol_26_30kph": 2,
            }
            for i in range(20)
        ]
    )
    data = normalize_speed_bins(raw)
    assert data.iloc[0].speed_kph == 25.25
    training, test = heldout_sites(data)
    assert not set(training.site_id) & set(test.site_id)
    assert (data.speed_bin_low_kph <= data.speed_kph).all()


def test_timestamp_timezone_dst_and_nonfinite_speed():
    frame = pd.DataFrame(
        {
            "observation_id": ["utc", "ambiguous", "nonexistent", "inf"],
            "latitude": [43.65] * 4,
            "longitude": [-79.38] * 4,
            "datetime": [
                "2025-07-01T11:00:00Z",
                "2025-11-02 01:30",
                "2025-03-09 02:30",
                "2025-07-01 07:00",
            ],
            "speed_kph": [30, 30, 30, float("inf")],
        }
    )
    cleaned = clean_observations(frame)
    assert list(cleaned.observation_id) == ["utc"]
    assert cleaned.iloc[0].hour == 7


@pytest.mark.parametrize("fleet,requests", [(0, 0), (0, 10), (10, 0)])
def test_empty_populations_reconcile(fleet, requests):
    engine = create_engine({"simulation": {"fleet_size": fleet, "base_trip_count": requests}})
    engine.run()
    m = engine.last_snapshot["metrics"]
    assert m["completed_trips"] + m["in_progress_trips"] + m["unserved_trips"] == requests
    assert m["utilization_rate"] == 0
