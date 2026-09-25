"""Reproducible public-data evaluation; no automatic calibration claim."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from toronto_rideshare.manifest import file_checksum
from toronto_rideshare.traffic.public_data import (
    SOURCE_URL,
    error_metrics,
    evaluate_speed_baselines,
    heldout_sites,
    normalize_speed_bins,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/midblock_speed_sample.csv")
    parser.add_argument("--graph", default="data/processed/toronto_drive.graphml")
    parser.add_argument("--output", default="results/public_data_evaluation.json")
    args = parser.parse_args()
    observations = normalize_speed_bins(pd.read_csv(args.input))
    report = evaluate_speed_baselines(observations)
    report["qa"] = observations.attrs["qa"]
    report["provenance"] = {
        "source_url": SOURCE_URL,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "license": "Open Government Licence – Toronto",
        "input": args.input,
        "sha256": file_checksum(args.input),
        "sampling": "Bounded first 50,000 raw records; not a representative city sample",
    }
    if Path(args.graph).exists():
        from toronto_rideshare.network import load_graph
        from toronto_rideshare.traffic.map_to_edges import (
            graph_edges_gdf,
            map_observations_to_edges,
        )

        graph = load_graph(args.graph)
        edges = graph_edges_gdf(graph)
        training, test = heldout_sites(observations)
        mapped = map_observations_to_edges(test, edges)
        usable = mapped[~mapped.ambiguous_match]
        merged = usable.merge(test[["observation_id", "speed_kph"]], on="observation_id")
        predictions = [
            float(graph.edges[int(r.u), int(r.v), int(r.key)]["speed_kph"])
            for r in merged.itertuples()
        ]
        report["mapping"] = {
            "test_rows": len(test),
            "mapped_rows": len(mapped),
            "unambiguous_rows": len(usable),
            "maximum_distance_m": 50,
            "direction": "directional candidates, ambiguous ties excluded",
        }
        if predictions:
            report["free_flow"] = error_metrics(merged.speed_kph, predictions)
        from toronto_rideshare.traffic import build_traffic_profile, save_traffic_profile

        profile, training_map = build_traffic_profile(graph, training)
        save_traffic_profile(profile, "data/processed/observed_training_profile.parquet")
        joined = merged.merge(test[["observation_id", "time_bucket"]], on="observation_id")
        predicted = joined.merge(
            profile.edge_stats[["u", "v", "key", "time_bucket", "observed_speed_kph"]],
            on=["u", "v", "key", "time_bucket"],
            validate="many_to_one",
        )
        if len(predicted):
            medians = training.groupby("time_bucket").speed_kph.median()
            report["matched_cohort"] = {
                "n": len(predicted),
                "traffic_profile": error_metrics(predicted.speed_kph, predicted.observed_speed_kph),
                "time_bucket_median": error_metrics(
                    predicted.speed_kph,
                    predicted.time_bucket.map(medians).fillna(training.speed_kph.median()),
                ),
                "free_flow": error_metrics(
                    predicted.speed_kph,
                    [
                        float(graph.edges[int(r.u), int(r.v), int(r.key)]["speed_kph"])
                        for r in predicted.itertuples()
                    ],
                ),
            }
        report["training_profile"] = {
            "rows": len(profile.edge_stats),
            "source_counts": profile.edge_stats.cost_source.value_counts().to_dict(),
            "mapped_observations": len(training_map),
            "sha256": file_checksum("data/processed/observed_training_profile.parquet"),
        }
        report["provenance"]["graph_sha256"] = file_checksum(args.graph)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
