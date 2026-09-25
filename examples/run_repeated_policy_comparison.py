"""Run a fair repeated-seed P0-P7 comparison with confidence intervals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from toronto_rideshare.experiments import run_repeated_policy_comparison


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", default="configs/experiments/baseline_run.yaml"
    )
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--no-routing", action="store_true")
    parser.add_argument(
        "--output",
        default="artifacts/task_policy_compare/repeated_policy_comparison.json",
    )
    args = parser.parse_args()
    result = run_repeated_policy_comparison(
        args.config,
        n_replicates=args.replicates,
        load_configured_routing=not args.no_routing,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(output.resolve())


if __name__ == "__main__":
    main()
