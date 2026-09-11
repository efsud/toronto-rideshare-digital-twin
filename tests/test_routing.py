from __future__ import annotations

import math

import networkx as nx
import pytest

from toronto_rideshare.network.routing import summarize_route


def make_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    # Parallel edges 1->2: the routing summary should select the faster one.
    graph.add_edge(1, 2, length=1000.0, travel_time=120.0)
    graph.add_edge(1, 2, length=900.0, travel_time=90.0)
    graph.add_edge(2, 3, length=2100.0, travel_time=210.0)
    return graph


def test_summarize_route_uses_fastest_parallel_edge() -> None:
    result = summarize_route(make_graph(), [1, 2, 3])

    assert result.route_nodes == [1, 2, 3]
    assert result.origin_node == 1
    assert result.destination_node == 3
    assert math.isclose(result.distance_km, 3.0)
    assert math.isclose(result.travel_time_min, 5.0)


def test_route_requires_two_nodes() -> None:
    with pytest.raises(ValueError, match="at least two nodes"):
        summarize_route(make_graph(), [1])


def test_missing_edge_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="missing directed edge"):
        summarize_route(make_graph(), [1, 3])
