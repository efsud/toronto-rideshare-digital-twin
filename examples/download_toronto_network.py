"""Download Toronto's drivable OSM network and cache it as GraphML."""

from toronto_rideshare.network import build_drive_network, save_graph


def main() -> None:
    graph = build_drive_network()
    path = save_graph(graph, "data/processed/toronto_drive.graphml")
    print(f"Saved Toronto drive graph to: {path}")
    print(f"Nodes: {graph.number_of_nodes():,}")
    print(f"Directed edges: {graph.number_of_edges():,}")


if __name__ == "__main__":
    main()
