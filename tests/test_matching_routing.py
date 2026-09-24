from __future__ import annotations

import builtins
import math

import networkx as nx
import pandas as pd

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.marketplace.matching import (
    RoutingContext,
    batch_assign,
    estimate_route,
    greedy_match,
    min_to_departure_time,
)
from toronto_rideshare.supply.models import Driver
from toronto_rideshare.traffic.models import TrafficProfile


def make_routing_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.add_node(1, x=-79.4000, y=43.6500)
    graph.add_node(2, x=-79.3950, y=43.6500)
    graph.add_node(3, x=-79.3900, y=43.6500)
    graph.add_edge(1, 2, 0, length=500.0, travel_time=60.0, highway="primary")
    graph.add_edge(2, 3, 0, length=500.0, travel_time=60.0, highway="primary")
    graph.graph["crs"] = "epsg:4326"
    return graph


def make_profile() -> TrafficProfile:
    rows = [
        {
            "u": 1,
            "v": 2,
            "key": 0,
            "time_bucket": "07:00",
            "observed_speed_kph": 30.0,
            "free_flow_speed_kph": 30.0,
            "travel_time_s": 120.0,
            "congestion_ratio": 2.0,
            "n_observations": 1,
        },
        {
            "u": 2,
            "v": 3,
            "key": 0,
            "time_bucket": "07:00",
            "observed_speed_kph": 30.0,
            "free_flow_speed_kph": 30.0,
            "travel_time_s": 60.0,
            "congestion_ratio": 1.0,
            "n_observations": 1,
        },
    ]
    return TrafficProfile(edge_stats=pd.DataFrame(rows), time_buckets=("07:00",))


def test_min_to_departure_time() -> None:
    assert min_to_departure_time(7 * 60) == "07:00"
    assert min_to_departure_time(7 * 60 + 30) == "07:30"


def test_greedy_match_with_network_routing() -> None:
    trip = TripRequest(
        request_id="R1",
        request_time_min=0.0,
        origin_lat=43.6500,
        origin_lon=-79.4000,
        destination_lat=43.6500,
        destination_lon=-79.3900,
        origin_zone="z1",
        destination_zone="z2",
    )
    driver = Driver(driver_id="D1", lat=43.6500, lon=-79.4000, zone="z1")
    routing = RoutingContext(graph=make_routing_graph(), profile=make_profile())

    matches = greedy_match([trip], [driver], current_time_min=7 * 60, routing=routing)
    assert len(matches) == 1
    _, _, pickup_min, trip_min, fare = matches[0]
    assert pickup_min >= 0.0
    assert trip_min > 0.0
    assert fare.rider_payment_cad > 0.0


def test_greedy_match_haversine_fallback_without_routing() -> None:
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
    assert math.isfinite(matches[0][2])


def test_off_bucket_time_snaps_without_haversine_fallback() -> None:
    routing = RoutingContext(graph=make_routing_graph(), profile=make_profile())
    result = estimate_route(
        (43.6500, -79.4000),
        (43.6500, -79.3900),
        routing=routing,
        departure_time="07:17",
    )
    assert result.mode == "time-dependent network"
    assert result.fallback_reason is None
    assert result.travel_time_min == 3.0


def test_time_dependent_parallel_edge_key_controls_distance_and_time() -> None:
    graph = nx.MultiDiGraph()
    graph.add_node(1, x=-79.4000, y=43.6500)
    graph.add_node(2, x=-79.3900, y=43.6500)
    graph.add_edge(1, 2, 0, length=500.0, travel_time=30.0)
    graph.add_edge(1, 2, 1, length=900.0, travel_time=60.0)
    graph.graph["crs"] = "epsg:4326"
    rows = []
    for key, travel_time_s in ((0, 300.0), (1, 45.0)):
        rows.append(
            {
                "u": 1,
                "v": 2,
                "key": key,
                "time_bucket": "07:00",
                "observed_speed_kph": 30.0,
                "free_flow_speed_kph": 30.0,
                "travel_time_s": travel_time_s,
                "congestion_ratio": 1.0,
                "n_observations": 1,
            }
        )
    routing = RoutingContext(
        graph=graph,
        profile=TrafficProfile(pd.DataFrame(rows), time_buckets=("07:00",)),
    )

    result = estimate_route(
        (43.6500, -79.4000),
        (43.6500, -79.3900),
        routing=routing,
        departure_time="07:05",
    )

    assert result.mode == "time-dependent network"
    assert result.distance_km == 0.9
    assert result.travel_time_min == 0.75


def test_no_directed_path_reports_haversine_fallback_reason() -> None:
    graph = make_routing_graph()
    routing = RoutingContext(graph=graph, use_time_dependent=False)

    result = estimate_route(
        (43.6500, -79.3900),
        (43.6500, -79.4000),
        routing=routing,
        departure_time="12:34",
    )

    assert result.mode == "haversine fallback"
    assert "NetworkXNoPath" in (result.fallback_reason or "")
    assert result.distance_km > 0.0


def test_origin_equals_destination_remains_network_routed() -> None:
    routing = RoutingContext(graph=make_routing_graph(), use_time_dependent=False)

    result = estimate_route(
        (43.6500, -79.4000),
        (43.6500, -79.4000),
        routing=routing,
        departure_time="12:34",
    )

    assert result.mode == "network free-flow"
    assert result.fallback_reason is None
    assert result.distance_km == 0.0
    assert result.travel_time_min == 0.0


def test_batch_assignment_improves_pickup_and_is_deterministic() -> None:
    trips = [
        TripRequest("R1", 0.0, 43.65, -79.40, 43.65, -79.40, "z", "z"),
        TripRequest("R2", 0.0, 43.65, -79.39, 43.65, -79.39, "z", "z"),
    ]
    drivers = [
        Driver("D1", 43.65, -79.394, "z"),
        Driver("D2", 43.65, -79.407, "z"),
    ]
    optimized = batch_assign(trips, drivers, 0.0)
    replay = batch_assign(list(reversed(trips)), list(reversed(drivers)), 0.0)

    assert optimized.backend == "ortools-scip"
    assert optimized.pairs == replay.pairs
    assert optimized.pairs[0][1] == "D2"
    assert optimized.total_pickup_min < 3.0

    fallback = batch_assign(trips, drivers, 0.0, use_ortools=False)
    assert fallback.backend == "deterministic-greedy"
    assert (
        fallback.pairs
        == batch_assign(
            list(reversed(trips)),
            list(reversed(drivers)),
            0.0,
            use_ortools=False,
        ).pairs
    )


def test_batch_assignment_reports_ortools_import_fallback(monkeypatch) -> None:
    real_import = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name == "ortools.linear_solver":
            raise ImportError("simulated missing optional dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", unavailable)
    trip = TripRequest("R1", 0.0, 43.65, -79.40, 43.65, -79.39, "z", "z")
    driver = Driver("D1", 43.65, -79.40, "z")
    result = batch_assign([trip], [driver], 0.0)
    assert result.backend == "deterministic-greedy-fallback"
    assert "simulated missing" in (result.fallback_reason or "")
