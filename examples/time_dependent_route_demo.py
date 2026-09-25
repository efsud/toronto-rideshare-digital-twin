"""Compare routes for the same OD pair at different departure times."""

from pathlib import Path

from toronto_rideshare.config import load_config
from toronto_rideshare.network import load_graph
from toronto_rideshare.traffic import (
    DEFAULT_TIME_BUCKETS,
    load_traffic_profile,
    shortest_time_route_at,
)

CONFIG_PATH = Path("configs/morning_peak.yaml")
PROFILE_PATH = Path("data/processed/edge_traffic_profile.parquet")

ORIGIN = (43.7735, -79.5019)
DESTINATION = (43.6535, -79.3839)


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

    print(f"Origin: {ORIGIN}")
    print(f"Destination: {DESTINATION}")
    print(f"Traffic scenario: {config.get('traffic', {}).get('scenario', 'unknown')}")
    print()

    for departure_time in DEFAULT_TIME_BUCKETS:
        result = shortest_time_route_at(
            graph,
            ORIGIN,
            DESTINATION,
            profile,
            departure_time,
        )
        print(f"Departure {departure_time}")
        print(f"  Route nodes: {len(result.route_nodes):,}")
        print(f"  Distance: {result.distance_km:.2f} km")
        print(f"  Travel time: {result.travel_time_min:.1f} min")
        print()


if __name__ == "__main__":
    main()
