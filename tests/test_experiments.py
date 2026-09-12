from toronto_rideshare.experiments import run_experiment


def test_run_experiment_baseline() -> None:
    result = run_experiment("configs/experiments/baseline_run.yaml")
    assert "metrics" in result
    assert result["metrics"]["completed_trips"] >= 0
