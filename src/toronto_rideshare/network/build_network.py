"""Build and persist the Toronto drive network using OSMnx."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx

DEFAULT_HIGHWAY_SPEEDS_KPH: dict[str, float] = {
    "motorway": 100.0,
    "motorway_link": 60.0,
    "trunk": 80.0,
    "trunk_link": 50.0,
    "primary": 50.0,
    "primary_link": 40.0,
    "secondary": 50.0,
    "secondary_link": 40.0,
    "tertiary": 40.0,
    "tertiary_link": 35.0,
    "residential": 30.0,
    "living_street": 20.0,
    "service": 20.0,
    "unclassified": 30.0,
}


def _ox() -> Any:
    """Import OSMnx lazily so lightweight unit tests do not require network access."""
    import osmnx as ox

    return ox


def build_drive_network(
    place: str = "Toronto, Ontario, Canada",
    *,
    network_type: str = "drive",
    simplify: bool = True,
    retain_all: bool = False,
    fallback_speed_kph: float = 35.0,
    highway_speeds_kph: dict[str, float] | None = None,
) -> nx.MultiDiGraph:
    """Download a drivable OSM network and add free-flow speed/travel-time attributes.

    Notes
    -----
    The returned ``travel_time`` is a *free-flow/base* travel time. A later traffic
    module will create time-dependent edge costs such as ``travel_time_t`` from
    observed Toronto traffic data.
    """
    ox = _ox()
    speeds = DEFAULT_HIGHWAY_SPEEDS_KPH.copy()
    if highway_speeds_kph:
        speeds.update(highway_speeds_kph)

    graph = ox.graph.graph_from_place(
        place,
        network_type=network_type,
        simplify=simplify,
        retain_all=retain_all,
    )
    graph = ox.routing.add_edge_speeds(
        graph,
        hwy_speeds=speeds,
        fallback=fallback_speed_kph,
    )
    graph = ox.routing.add_edge_travel_times(graph)
    return graph


def save_graph(graph: nx.MultiDiGraph, path: str | Path) -> Path:
    """Save an OSMnx graph as GraphML and return the resolved path."""
    ox = _ox()
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ox.io.save_graphml(graph, filepath=output_path)
    return output_path.resolve()


def load_graph(path: str | Path) -> nx.MultiDiGraph:
    """Load a GraphML network previously saved by :func:`save_graph`."""
    ox = _ox()
    return ox.io.load_graphml(filepath=Path(path))
