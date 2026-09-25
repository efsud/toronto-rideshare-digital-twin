from pathlib import Path

import yaml

from toronto_rideshare.experiments import run_experiment, run_repeated_policy_comparison
from toronto_rideshare.policies.registry import PolicyId


def test_run_experiment_baseline() -> None:
    result = run_experiment(
        "configs/experiments/baseline_run.yaml",
        load_configured_routing=False,
    )
    assert "metrics" in result
    assert result["metrics"]["completed_trips"] >= 0
    metrics = result["metrics"]
    assert (
        metrics["completed_trips"]
        + metrics["unserved_arrived_trips"]
        + metrics["in_progress_trips"]
        == result["generated_trip_count"] - metrics["not_yet_released_trips"]
    )


def test_run_experiment_honors_start_time_and_single_demand_scaling(tmp_path) -> None:
    config = yaml.safe_load(
        Path("configs/experiments/baseline_run.yaml").read_text(encoding="utf-8")
    )
    config["simulation"].update(
        start_time="08:30",
        end_time="08:35",
        base_trip_count=10,
        demand_multiplier=1.5,
    )
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")

    result = run_experiment(path, load_configured_routing=False)

    assert result["simulation_start_time_min"] == 510.0
    assert result["generated_trip_count"] == 15
    assert result["policy_strategy"]
    assert result["policy_objective"]
    assert result["policy_assumptions"]["rider_max_wait_minutes"] == 15.0


def test_repeated_policy_comparison_uses_common_seeds_and_intervals() -> None:
    result = run_repeated_policy_comparison(
        "configs/experiments/baseline_run.yaml",
        policies=(PolicyId.P0, PolicyId.P1),
        n_replicates=2,
        base_seed=17,
        load_configured_routing=False,
    )

    assert result["seeds"] == [17, 18]
    assert result["common_random_numbers"] is True
    assert len(result["replicates"]) == 4
    assert {row["random_seed"] for row in result["replicates"]} == {17, 18}
    assert len(result["aggregates"]) == 2
    service = result["aggregates"][0]["metrics"]["service_rate"]
    assert service["ci95_low"] <= service["mean"] <= service["ci95_high"]
