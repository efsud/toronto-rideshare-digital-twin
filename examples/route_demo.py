"""Route between two Toronto points using free-flow travel time."""

from pathlib import Path

from toronto_rideshare.network import load_graph, shortest_time_route

GRAPH_PATH = Path("data/processed/toronto_drive.graphml")

# Example only. Replace with any Toronto coordinates you want to test.
ORIGIN = (43.7735, -79.5019)       # York University area
DESTINATION = (43.6535, -79.3839)  # Toronto City Hall area


def main() -> None:
    if not GRAPH_PATH.exists():
        raise FileNotFoundError(
            f"{GRAPH_PATH} does not exist. Run examples/download_toronto_network.py first."
        )

    graph = load_graph(GRAPH_PATH)
    result = shortest_time_route(graph, ORIGIN, DESTINATION)

    print(f"Origin node: {result.origin_node}")
    print(f"Destination node: {result.destination_node}")
    print(f"Distance: {result.distance_km:.2f} km")
    print(f"Free-flow travel time: {result.travel_time_min:.1f} min")
    print(f"Route nodes: {len(result.route_nodes):,}")


if __name__ == "__main__":
    main()
