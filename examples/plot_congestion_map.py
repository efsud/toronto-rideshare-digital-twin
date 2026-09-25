"""Plot median congestion ratio by edge for one departure bucket."""

from pathlib import Path

import matplotlib.pyplot as plt

from toronto_rideshare.config import load_config
from toronto_rideshare.network import load_graph
from toronto_rideshare.traffic import load_traffic_profile

CONFIG_PATH = Path("configs/morning_peak.yaml")
OUTPUT_PATH = Path("artifacts/task_05_congestion/congestion_map_0830.png")
DEPARTURE = "08:30"


def _ox():
    import osmnx as ox

    return ox


def main() -> None:
    config = load_config(CONFIG_PATH)
    graph_path = Path(config["network"]["graph_path"])
    profile_path = Path(config["traffic"]["profile_path"])
    if not graph_path.exists() or not profile_path.exists():
        raise FileNotFoundError(
            "Run download_toronto_network.py and build_traffic_profile.py first."
        )

    graph = load_graph(graph_path)
    profile = load_traffic_profile(profile_path)
    bucket = profile.edge_stats[profile.edge_stats["time_bucket"] == DEPARTURE].copy()
    lookup = {
        (int(r.u), int(r.v), int(r.key)): float(r.congestion_ratio)
        for r in bucket.itertuples(index=False)
    }

    for u, v, key, data in graph.edges(keys=True, data=True):
        data["congestion_ratio"] = lookup.get((int(u), int(v), int(key)), 1.0)

    ox = _ox()
    _, edges = ox.convert.graph_to_gdfs(graph)
    fig, ax = plt.subplots(figsize=(10, 10))
    edges.plot(column="congestion_ratio", ax=ax, legend=True, cmap="YlOrRd", linewidth=0.4)
    ax.set_title(f"Congestion ratio at {DEPARTURE} (1.0 = free-flow)")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=150)
    print(f"Saved {OUTPUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
