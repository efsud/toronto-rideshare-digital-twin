"""Build a time-dependent edge traffic profile from observation data."""

from pathlib import Path

from toronto_rideshare.config import load_config
from toronto_rideshare.network import load_graph
from toronto_rideshare.traffic import build_traffic_profile_from_file, save_traffic_profile

DEFAULT_CONFIG = Path("configs/morning_peak.yaml")
DEFAULT_OBSERVATIONS = Path("data/synthetic/traffic_observations_sample.csv")
PROFILE_PATH = Path("data/processed/edge_traffic_profile.parquet")
EDGE_MAP_PATH = Path("data/processed/traffic_edge_map.parquet")


def main() -> None:
    config = load_config(DEFAULT_CONFIG)
    graph_path = Path(config["network"]["graph_path"])
    if not graph_path.exists():
        raise FileNotFoundError(
            f"{graph_path} does not exist. Run examples/download_toronto_network.py first."
        )

    observations_path = Path(
        config.get("traffic", {}).get("observations_path", DEFAULT_OBSERVATIONS)
    )
    if not observations_path.exists():
        raise FileNotFoundError(
            f"{observations_path} does not exist. See data/raw/README.md for download instructions."
        )

    graph = load_graph(graph_path)
    profile, mapping = build_traffic_profile_from_file(graph, observations_path)

    save_traffic_profile(profile, PROFILE_PATH)
    EDGE_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_parquet(EDGE_MAP_PATH, index=False)

    print(f"Saved traffic profile to: {PROFILE_PATH.resolve()}")
    print(f"Saved edge map to: {EDGE_MAP_PATH.resolve()}")
    print(f"Profile rows: {len(profile.edge_stats):,}")
    print(f"Mapped observations: {len(mapping):,}")


if __name__ == "__main__":
    main()
