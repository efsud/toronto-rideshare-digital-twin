"""Travel-time routing over the Toronto road network."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx


@dataclass(frozen=True, slots=True)
class RouteResult:
    """Summary of one minimum-travel-time route."""

    route_nodes: list[int]
    origin_node: int
    destination_node: int
    distance_km: float
    travel_time_min: float


def _ox() -> Any:
    import osmnx as ox

    return ox


def _best_parallel_edge_data(
    graph: nx.MultiDiGraph,
    u: int,
    v: int,
    *,
    weight: str,
) -> dict[str, Any]:
    """Return data for the minimum-weight parallel edge between ``u`` and ``v``."""
    edge_bundle = graph.get_edge_data(u, v)
    if not edge_bundle:
        raise ValueError(f"Route contains missing directed edge {u!r} -> {v!r}.")

    candidates = list(edge_bundle.values())
    try:
        return min(candidates, key=lambda data: float(data[weight]))
    except KeyError as exc:
        raise KeyError(f"Edge {u!r}->{v!r} is missing required weight '{weight}'.") from exc


def summarize_route(
    graph: nx.MultiDiGraph,
    route_nodes: list[int],
    *,
    weight: str = "travel_time",
) -> RouteResult:
    """Calculate distance and travel time for an already-computed route.

    This helper is intentionally independent of OSMnx so it can be unit-tested
    using tiny synthetic NetworkX graphs.
    """
    if len(route_nodes) < 2:
        raise ValueError("A route must contain at least two nodes.")

    distance_m = 0.0
    travel_time_s = 0.0
    for u, v in zip(route_nodes[:-1], route_nodes[1:], strict=True):
        edge = _best_parallel_edge_data(graph, u, v, weight=weight)
        if "length" not in edge:
            raise KeyError(f"Edge {u!r}->{v!r} is missing required 'length'.")
        if weight not in edge:
            raise KeyError(f"Edge {u!r}->{v!r} is missing required weight '{weight}'.")
        distance_m += float(edge["length"])
        travel_time_s += float(edge[weight])

    return RouteResult(
        route_nodes=list(route_nodes),
        origin_node=int(route_nodes[0]),
        destination_node=int(route_nodes[-1]),
        distance_km=distance_m / 1000.0,
        travel_time_min=travel_time_s / 60.0,
    )


def shortest_time_route(
    graph: nx.MultiDiGraph,
    origin_latlon: tuple[float, float],
    destination_latlon: tuple[float, float],
    *,
    weight: str = "travel_time",
) -> RouteResult:
    """Find the minimum-time route between two latitude/longitude coordinates.

    Parameters
    ----------
    graph:
        OSMnx/NetworkX directed road graph with ``length`` and ``travel_time``
        edge attributes.
    origin_latlon, destination_latlon:
        ``(latitude, longitude)`` pairs.
    weight:
        Edge attribute minimized by the shortest-path algorithm. Version 1 uses
        ``travel_time``. Later traffic modules can pass a dynamic travel-time
        attribute instead.
    """
    ox = _ox()
    origin_lat, origin_lon = origin_latlon
    destination_lat, destination_lon = destination_latlon

    origin_node = int(ox.distance.nearest_nodes(graph, X=origin_lon, Y=origin_lat))
    destination_node = int(
        ox.distance.nearest_nodes(graph, X=destination_lon, Y=destination_lat)
    )

    route = ox.routing.shortest_path(
        graph,
        origin_node,
        destination_node,
        weight=weight,
    )
    if route is None:
        raise nx.NetworkXNoPath(
            f"No directed path from nearest origin node {origin_node} "
            f"to destination node {destination_node}."
        )

    return summarize_route(graph, list(route), weight=weight)
