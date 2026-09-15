from toronto_rideshare.experiments import run_policy_comparison
from toronto_rideshare.policies.registry import PolicyId


def test_run_policy_comparison_same_seed() -> None:
    result = run_policy_comparison(
        "configs/experiments/baseline_run.yaml",
        policies=(PolicyId.P0, PolicyId.P1, PolicyId.P3),
        load_configured_routing=False,
    )
    assert len(result["results"]) == 3
    seeds = {r["random_seed"] for r in result["results"]}
    assert len(seeds) == 1
