"""Fit a deployable road-speed parameter profile using a site-disjoint public holdout."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from toronto_rideshare.calibration import fit_speed_scales, predict_speeds
from toronto_rideshare.manifest import file_checksum
from toronto_rideshare.network import load_graph
from toronto_rideshare.traffic.map_to_edges import graph_edges_gdf, map_observations_to_edges
from toronto_rideshare.traffic.models import DEFAULT_TIME_BUCKETS, TrafficProfile
from toronto_rideshare.traffic.public_data import (
    SOURCE_URL,
    error_metrics,
    heldout_sites,
    normalize_speed_bins,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/midblock_speed_sample.csv")
    parser.add_argument("--graph", default="data/processed/toronto_drive.graphml")
    parser.add_argument("--profile", default="data/processed/calibrated_speed_profile.parquet")
    parser.add_argument("--report", default="results/speed_calibration.json")
    args = parser.parse_args()
    graph = load_graph(args.graph)
    observations = normalize_speed_bins(pd.read_csv(args.input))
    training, test = heldout_sites(observations)
    edges = graph_edges_gdf(graph)

    def matched(frame):
        mapping = map_observations_to_edges(frame, edges)
        usable = mapping[~mapping.ambiguous_match]
        joined = usable.merge(
            frame[["observation_id", "site_id", "time_bucket", "speed_kph"]],
            on="observation_id",
            validate="one_to_one",
        )
        joined["free_flow_speed_kph"] = [
            float(graph.edges[int(r.u), int(r.v), int(r.key)]["speed_kph"])
            for r in joined.itertuples()
        ]
        return joined

    train_matched, test_matched = matched(training), matched(test)
    fit = fit_speed_scales(train_matched)
    report = {
        "status": "calibrated_speed_parameters_with_holdout",
        "fit": fit,
        "scope": "spot speed-bin midpoints; not OD travel times or ride-hailing behavior",
        "training_rows_before_mapping": len(training),
        "test_rows_before_mapping": len(test),
        "test_rows_mapped": len(test_matched),
        "training_sites": sorted(train_matched.site_id.unique()),
        "test_sites": sorted(test_matched.site_id.unique()),
        "group_overlap": sorted(set(training.site_id) & set(test.site_id)),
        "calibrated": error_metrics(test_matched.speed_kph, predict_speeds(test_matched, fit)),
        "free_flow": error_metrics(test_matched.speed_kph, test_matched.free_flow_speed_kph),
        "acceptance_criteria": None,
        "evaluation_design": (
            "Exploratory reuse of prior site holdout; fresh external evaluation remains necessary"
        ),
        "provenance": {
            "url": SOURCE_URL,
            "evaluated_at": datetime.now(UTC).isoformat(),
            "input_sha256": file_checksum(args.input),
            "graph_sha256": file_checksum(args.graph),
            "sampling": "First 50,000 source rows; not a representative city sample",
        },
        "uncalibrated": [
            "ride demand",
            "rider price response",
            "driver choice",
            "fleet distribution",
        ],
    }
    rows = []
    for bucket in DEFAULT_TIME_BUCKETS:
        scale = fit["bucket_scales"].get(bucket, fit["global_scale"])
        for u, v, key, edge in graph.edges(keys=True, data=True):
            free = float(edge["speed_kph"])
            speed = free * scale
            rows.append(
                {
                    "u": u,
                    "v": v,
                    "key": key,
                    "time_bucket": bucket,
                    "observed_speed_kph": speed,
                    "free_flow_speed_kph": free,
                    "travel_time_s": float(edge["length"]) * 3.6 / speed,
                    "congestion_ratio": 1 / scale,
                    "n_observations": 0,
                    "cost_source": "calibrated_bucket_prediction",
                }
            )
    TrafficProfile(pd.DataFrame(rows)).save(args.profile)
    report["profile_sha256"] = file_checksum(args.profile)
    report["profile_path"] = args.profile
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2))
    Path(args.profile).with_suffix(".calibration.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ("training_sites", "test_sites")}, indent=2
        )
    )


if __name__ == "__main__":
    main()
