"""Portable run evidence, independent of dashboard presentation."""

import hashlib
import subprocess
from pathlib import Path

from toronto_rideshare.scenario import stream_seed

METRIC_DEFINITIONS = {
    "service_rate": "Completed by horizon / arrived potential requests",
    "mean_wait_min": "Request-to-pickup minutes, riders actually collected only",
    "utilization_rate": "Elapsed pickup + occupied minutes / fleet minutes; excludes repositioning",
    "total_driver_earnings_cad": "Gross earnings; excludes vehicle expenses",
    "platform_net_revenue_cad": (
        "Rider payments minus gross driver earnings; before operating costs"
    ),
    "total_pickup_time_min": "Planned pickup duration for accepted assignments",
    "total_trip_time_min": "Planned occupied duration for accepted assignments",
    "total_reposition_time_min": "Planned reposition duration",
    "unserved_trips": "Cancelled + price declined + still waiting at horizon",
}


def file_checksum(path):
    candidate = Path(path)
    if not candidate.is_file():
        return None
    digest = hashlib.sha256()
    with candidate.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_manifest(config, engine):
    root = Path(__file__).resolve().parents[2]
    git = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    network = config["network"]
    seed = config["project"]["random_seed"]
    return {
        "schema_version": 2,
        "model_version": "0.5.0",
        "commit": git.stdout.strip() or None,
        "working_tree_dirty": bool(status.stdout.strip()),
        "scenario": config,
        "source_checksums": {
            name: file_checksum(network[name]) for name in ("graph_path", "traffic_profile_path")
        },
        "random_streams": {
            name: seed
            if config["behavior"]["profile"] == "legacy_v0.4"
            and name in ("demand", "fleet", "behavior")
            else stream_seed(seed, name)
            for name in ("demand", "fleet", "behavior", "network_demand", "network_fleet")
        },
        "matching_backend": engine.last_snapshot["matching_backend"],
        "pricing_decisions": [
            e["diagnostics"] for e in engine.events if e["type"] == "policy_decision"
        ],
        "population_sampling": (
            "uniform eligible road nodes"
            if engine.routing and engine.routing.strict
            else "uniform clipped H3 cells"
        ),
        "routing_mode_counts": engine.metrics.routing_mode_counts,
        "metric_definitions": METRIC_DEFINITIONS,
        "data_status": {
            "demand": "synthetic uniform",
            "behavior": "assumed",
            "traffic": "profile supplied; inspect provenance"
            if engine.routing and engine.routing.profile
            else "no observed traffic profile",
            "empirical_validation": "not_evaluated",
        },
    }
