"""Plot time-dependent routes and travel times for one OD pair."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from toronto_rideshare.config import load_config
from toronto_rideshare.network import load_graph
from toronto_rideshare.traffic import (
    DEFAULT_TIME_BUCKETS,
    load_traffic_profile,
    shortest_time_route_at,
)

CONFIG_PATH = Path("configs/morning_peak.yaml")
PROFILE_PATH = Path("data/processed/edge_traffic_profile.parquet")
OUTPUT_PATH = Path("figures/time_dependent_routes_york_to_cityhall.png")

ORIGIN = (43.7735, -79.5019)
DESTINATION = (43.6535, -79.3839)
COLORS = {"07:00": "#1f77b4", "08:30": "#ff7f0e", "12:00": "#2ca02c", "17:00": "#d62728"}


def _ox():
    import osmnx as ox

    return ox


def main() -> None:
    config = load_config(CONFIG_PATH)
    graph_path = Path(config["network"]["graph_path"])
    if not graph_path.exists():
        raise FileNotFoundError(
            f"{graph_path} does not exist. Run examples/download_toronto_network.py first."
        )
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(
            f"{PROFILE_PATH} does not exist. Run examples/build_traffic_profile.py first."
        )

    graph = load_graph(graph_path)
    profile = load_traffic_profile(PROFILE_PATH)
    ox = _ox()

    fig, (ax_map, ax_bar) = plt.subplots(
        1,
        2,
        figsize=(14, 6),
        gridspec_kw={"width_ratios": [2.2, 1.0]},
    )

    travel_times_min: list[float] = []
    labels: list[str] = []

    for departure_time in DEFAULT_TIME_BUCKETS:
        result = shortest_time_route_at(
            graph,
            ORIGIN,
            DESTINATION,
            profile,
            departure_time,
        )
        route_graph = graph.subgraph(result.route_nodes).copy()
        route_edges = ox.convert.graph_to_gdfs(route_graph, nodes=False)
        route_edges.plot(
            ax=ax_map,
            color=COLORS[departure_time],
            linewidth=2.0,
            label=departure_time,
        )

        travel_times_min.append(result.travel_time_min)
        labels.append(departure_time)

    ax_map.set_title("Same trip, different departure times")
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")
    ax_map.legend(title="Departure")

    ax_bar.bar(labels, travel_times_min, color=[COLORS[label] for label in labels])
    ax_bar.set_title("Travel time by departure")
    ax_bar.set_ylabel("Minutes")
    ax_bar.set_xlabel("Departure time")

    fig.tight_layout()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=150)
    print(f"Saved figure to: {OUTPUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
