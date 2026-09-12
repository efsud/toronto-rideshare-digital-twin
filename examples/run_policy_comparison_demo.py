"""Run P0–P7 policy comparison and save JSON + chart."""

from __future__ import annotations

import json
from pathlib import Path

from toronto_rideshare.experiments import run_policy_comparison


def main() -> None:
    comparison = run_policy_comparison("configs/experiments/baseline_run.yaml")
    out_dir = Path("artifacts/task_policy_compare")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "policy_comparison.json"
    json_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(f"Saved {json_path}")

    try:
        import matplotlib.pyplot as plt

        policies = [r["policy_id"] for r in comparison["results"]]
        completed = [r["metrics"]["completed_trips"] for r in comparison["results"]]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(policies, completed, color="steelblue")
        ax.set_ylabel("Completed trips")
        ax.set_title("Policy comparison P0–P7 (same seed)")
        plt.xticks(rotation=45, ha="right")
        fig.tight_layout()
        chart_path = out_dir / "policy_comparison_chart.png"
        fig.savefig(chart_path, dpi=150)
        print(f"Saved {chart_path}")
    except ImportError:
        print("matplotlib not installed; skipped chart")


if __name__ == "__main__":
    main()
