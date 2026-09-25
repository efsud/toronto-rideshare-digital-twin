"""Record a reproducible demo scale envelope, without claiming network-scale performance."""

import json
import time
import tracemalloc
from pathlib import Path

from toronto_rideshare.experiments.runner import run_experiment, run_repeated_policy_comparison
from toronto_rideshare.scenario import ScenarioConfig


def main():
    output = Path("results/research_validation")
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for fleet, requests in ((20, 20), (100, 100), (200, 200)):
        config = ScenarioConfig.from_source({}).as_dict()
        config["simulation"].update(fleet_size=fleet, base_trip_count=requests)
        tracemalloc.start()
        start = time.perf_counter()
        result = run_experiment(config)
        seconds = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rows.append(
            {
                "fleet": fleet,
                "requests": requests,
                "seconds": seconds,
                "peak_python_mb": peak / 1e6,
                "routing": result["routing_mode"],
                "metrics": result["metrics"],
            }
        )
    (output / "scale.json").write_text(json.dumps(rows, indent=2))
    start = time.perf_counter()
    comparison = run_repeated_policy_comparison({}, n_replicates=30)
    comparison["runtime_seconds"] = time.perf_counter() - start
    (output / "paired_30_seeds.json").write_text(json.dumps(comparison, indent=2))
    print(
        json.dumps(
            {
                "scale": rows,
                "comparison_runs": len(comparison["replicates"]),
                "comparison_seconds": comparison["runtime_seconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
