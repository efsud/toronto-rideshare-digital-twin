"""Build a time-dependent edge traffic profile from observation data."""

from pathlib import Path

from toronto_rideshare.config import load_config
from toronto_rideshare.network import load_graph
from toronto_rideshare.traffic import build_traffic_profile_from_file, save_traffic_profile
from toronto_rideshare.traffic.ingest import load_traffic_observations, resolve_observations_path
from toronto_rideshare.traffic.qa import mapping_quality_report

DEFAULT_CONFIG = Path("configs/morning_peak.yaml")
PROFILE_PATH = Path("data/processed/edge_traffic_profile.parquet")
EDGE_MAP_PATH = Path("data/processed/traffic_edge_map.parquet")


def main() -> None:
    config = load_config(DEFAULT_CONFIG)
    graph_path = Path(config["network"]["graph_path"])
    if not graph_path.exists():
        raise FileNotFoundError(
            f"{graph_path} does not exist. Run examples/download_toronto_network.py first."
        )

    configured_path = config.get("traffic", {}).get("observations_path")
    observations_path = resolve_observations_path(configured_path)
    print(f"Using traffic observations: {observations_path.resolve()}")
    if "synthetic" in str(observations_path):
        print("  (synthetic fallback — place Toronto Open Data CSV in data/raw/ for real data)")

    graph = load_graph(graph_path)
    observations = load_traffic_observations(observations_path)
    profile, mapping = build_traffic_profile_from_file(graph, observations_path)

    qa = mapping_quality_report(mapping, observations, profile.edge_stats)
    save_traffic_profile(profile, PROFILE_PATH)
    EDGE_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_parquet(EDGE_MAP_PATH, index=False)

    print(f"Saved traffic profile to: {PROFILE_PATH.resolve()}")
    print(f"Saved edge map to: {EDGE_MAP_PATH.resolve()}")
    print(f"Profile rows: {len(profile.edge_stats):,}")
    print(f"Mapped observations: {len(mapping):,}")
    print("Mapping QA:")
    for key, value in qa.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
