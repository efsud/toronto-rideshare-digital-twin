"""Apply time-dependent travel times to a graph before routing."""

from __future__ import annotations

import networkx as nx

from toronto_rideshare.network.routing import RouteResult, shortest_time_route
from toronto_rideshare.traffic.models import DEFAULT_TIME_BUCKETS, TimeBucket, TrafficProfile

TRAVEL_TIME_T_ATTR = "travel_time_t"


def departure_time_to_bucket(
    departure_time: str,
    available_buckets: tuple[str, ...] | None = None,
) -> TimeBucket:
    """Snap a clock time to the nearest supported traffic bucket."""
    return TimeBucket.nearest(departure_time, available_buckets or DEFAULT_TIME_BUCKETS)


def get_edge_travel_time(
    graph: nx.MultiDiGraph,
    u: int,
    v: int,
    key: int,
    departure_time: str,
    profile: TrafficProfile,
) -> float:
    """Look up tau_e(t) for one directed edge."""
    bucket = departure_time_to_bucket(departure_time, profile.time_buckets).label
    travel_time_s = profile.lookup_travel_time_s(u, v, key, bucket)
    if travel_time_s is not None:
        return travel_time_s

    data = graph.edges[u, v, key]
    return float(data["travel_time"])


def apply_travel_times(
    graph: nx.MultiDiGraph,
    profile: TrafficProfile,
    departure_time: str,
) -> nx.MultiDiGraph:
    """Attach ``travel_time_t`` edge weights for the requested departure bucket."""
    bucket = departure_time_to_bucket(departure_time, profile.time_buckets).label
    bucket_stats = profile.edge_stats[profile.edge_stats["time_bucket"] == bucket]
    lookup = {
        (int(row.u), int(row.v), int(row.key)): float(row.travel_time_s)
        for row in bucket_stats.itertuples(index=False)
    }

    for u, v, key, data in graph.edges(keys=True, data=True):
        edge_key = (int(u), int(v), int(key))
        data[TRAVEL_TIME_T_ATTR] = lookup.get(edge_key, float(data["travel_time"]))

    return graph


def shortest_time_route_at(
    graph: nx.MultiDiGraph,
    origin_latlon: tuple[float, float],
    destination_latlon: tuple[float, float],
    profile: TrafficProfile,
    departure_time: str,
) -> RouteResult:
    """Find the minimum-time route for a specific departure time bucket."""
    weighted_graph = apply_travel_times(graph, profile, departure_time)
    return shortest_time_route(
        weighted_graph,
        origin_latlon,
        destination_latlon,
        weight=TRAVEL_TIME_T_ATTR,
    )
