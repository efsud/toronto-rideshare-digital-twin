"""Run baseline marketplace experiment from YAML."""

import argparse

from toronto_rideshare.experiments import run_experiment, save_experiment_result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-routing", action="store_true")
    args = parser.parse_args()
    result = run_experiment(
        "configs/experiments/baseline_run.yaml",
        load_configured_routing=not args.no_routing,
    )
    path = save_experiment_result(result, "results/experiments")
    print(f"Saved experiment result to {path}")
    print(result)


if __name__ == "__main__":
    main()
