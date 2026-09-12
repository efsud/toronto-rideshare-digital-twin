from __future__ import annotations

import math

import networkx as nx
import pandas as pd

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.marketplace.matching import (
    RoutingContext,
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
