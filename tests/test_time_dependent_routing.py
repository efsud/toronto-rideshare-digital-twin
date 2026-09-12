from __future__ import annotations

import math

import networkx as nx
import pandas as pd

from toronto_rideshare.traffic.apply import apply_travel_times, shortest_time_route_at
from toronto_rideshare.traffic.models import TrafficProfile


def make_routing_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.add_node(1, x=-79.4000, y=43.6500)
    graph.add_node(2, x=-79.3950, y=43.6500)
    graph.add_node(3, x=-79.3950, y=43.6450)
    graph.add_node(4, x=-79.3900, y=43.6500)

    graph.add_edge(1, 2, 0, length=500.0, travel_time=60.0, highway="primary")
    graph.add_edge(2, 4, 0, length=500.0, travel_time=60.0, highway="primary")
    graph.add_edge(1, 3, 0, length=500.0, travel_time=60.0, highway="secondary")
    graph.add_edge(3, 4, 0, length=500.0, travel_time=60.0, highway="secondary")
    graph.graph["crs"] = "epsg:4326"
    return graph


def make_profile() -> TrafficProfile:
    rows = []
    edge_times = {
        ("08:30", 1, 2, 0): 180.0,
        ("08:30", 2, 4, 0): 60.0,
        ("08:30", 1, 3, 0): 60.0,
        ("08:30", 3, 4, 0): 60.0,
        ("12:00", 1, 2, 0): 60.0,
        ("12:00", 2, 4, 0): 60.0,
        ("12:00", 1, 3, 0): 180.0,
        ("12:00", 3, 4, 0): 180.0,
    }
    for (bucket, u, v, key), travel_time_s in edge_times.items():
        rows.append(
            {
                "u": u,
                "v": v,
                "key": key,
                "time_bucket": bucket,
                "observed_speed_kph": 30.0,
                "free_flow_speed_kph": 30.0,
                "travel_time_s": travel_time_s,
                "congestion_ratio": travel_time_s / 60.0,
                "n_observations": 1,
            }
        )
    return TrafficProfile(edge_stats=pd.DataFrame(rows), time_buckets=("08:30", "12:00"))


def test_shortest_time_route_changes_with_departure_bucket() -> None:
    graph = make_routing_graph()
    profile = make_profile()
    origin = (43.6500, -79.4000)
    destination = (43.6500, -79.3900)

    morning = shortest_time_route_at(graph, origin, destination, profile, "08:30")
    midday = shortest_time_route_at(graph, origin, destination, profile, "12:00")

    assert morning.route_nodes == [1, 3, 4]
    assert midday.route_nodes == [1, 2, 4]
    assert math.isclose(morning.travel_time_min, 2.0)
    assert math.isclose(midday.travel_time_min, 2.0)


def test_apply_travel_times_sets_travel_time_t_attribute() -> None:
    graph = make_routing_graph()
    profile = make_profile()

    apply_travel_times(graph, profile, "08:30")

    assert graph.edges[1, 2, 0]["travel_time_t"] == 180.0
    assert graph.edges[1, 3, 0]["travel_time_t"] == 60.0
