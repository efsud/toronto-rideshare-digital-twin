"""Run baseline marketplace experiment from YAML."""

from toronto_rideshare.experiments import run_experiment, save_experiment_result


def main() -> None:
    result = run_experiment("configs/experiments/baseline_run.yaml")
    path = save_experiment_result(result, "results/experiments")
    print(f"Saved experiment result to {path}")
    print(result)


if __name__ == "__main__":
    main()
