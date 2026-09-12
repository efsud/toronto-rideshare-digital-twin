"""Generate demo artifacts: policy chart, sensitivity heatmap, matching comparison."""

from __future__ import annotations

import json
from pathlib import Path

from toronto_rideshare.experiments import (
    run_policy_comparison,
    run_sensitivity_analysis,
    run_stochastic_experiments,
)


def main() -> None:
    out_dir = Path("artifacts/task_demo")
    out_dir.mkdir(parents=True, exist_ok=True)

    comparison = run_policy_comparison("configs/experiments/baseline_run.yaml")
    (out_dir / "policy_comparison.json").write_text(
        json.dumps(comparison, indent=2), encoding="utf-8"
    )

    stochastic = run_stochastic_experiments(
        "configs/experiments/baseline_run.yaml", n_replicates=5
    )
    (out_dir / "stochastic_ci.json").write_text(
        json.dumps(stochastic, indent=2), encoding="utf-8"
    )

    sensitivity = run_sensitivity_analysis("configs/experiments/baseline_run.yaml")
    (out_dir / "sensitivity_grid.json").write_text(
        json.dumps(sensitivity, indent=2), encoding="utf-8"
    )

    try:
        import matplotlib.pyplot as plt
        import pandas as pd

        policies = [r["policy_id"] for r in comparison["results"]]
        completed = [r["metrics"]["completed_trips"] for r in comparison["results"]]
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        axes[0].bar(policies, completed, color="steelblue")
        axes[0].set_title("Policy comparison (P0–P7)")
        axes[0].tick_params(axis="x", rotation=45)

        grid_df = pd.DataFrame(sensitivity["grid"])
        pivot = grid_df.pivot(
            index="fleet_size", columns="demand_multiplier", values="completed_trips"
        )
        im = axes[1].imshow(pivot.values, aspect="auto", cmap="YlGnBu")
        axes[1].set_xticks(range(len(pivot.columns)))
        axes[1].set_xticklabels(pivot.columns)
        axes[1].set_yticks(range(len(pivot.index)))
        axes[1].set_yticklabels(pivot.index)
        axes[1].set_xlabel("Demand multiplier")
        axes[1].set_ylabel("Fleet size")
        axes[1].set_title("Sensitivity: completed trips")
        fig.colorbar(im, ax=axes[1])

        fig.tight_layout()
        chart_path = out_dir / "demo_summary.png"
        fig.savefig(chart_path, dpi=150)
        print(f"Saved {chart_path}")
    except ImportError:
        print("matplotlib not installed; JSON artifacts only")

    print(f"Demo artifacts written to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
