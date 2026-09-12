"""Run P0–P7 policy comparison and save chart artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from toronto_rideshare.experiments import run_policy_comparison, save_experiment_result

ARTIFACT_DIR = Path("artifacts/task_policy_compare")
CONFIG_PATH = "configs/experiments/baseline_run.yaml"


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    comparison = run_policy_comparison(CONFIG_PATH)
    json_path = ARTIFACT_DIR / "policy_comparison_p0_p7.json"
    json_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    save_experiment_result(comparison, ARTIFACT_DIR)

    rows = []
    for r in comparison["results"]:
        rows.append(
            {
                "policy": r["policy_id"].replace("_", "\n"),
                "completed_trips": r["metrics"]["completed_trips"],
                "unserved_trips": r["metrics"]["unserved_trips"],
                "mean_wait_min": r["mean_wait_min"],
                "rider_payment_cad": r["metrics"]["total_rider_payment_cad"],
                "driver_earnings_cad": r["metrics"]["total_driver_earnings_cad"],
                "network_routing": r.get("used_network_routing", False),
            }
        )
    df = pd.DataFrame(rows)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    axes[0].bar(df["policy"], df["completed_trips"], color="steelblue")
    axes[0].set_title("Completed trips by policy (same seed)")
    axes[0].set_ylabel("Trips")
    axes[0].tick_params(axis="x", labelsize=7)

    axes[1].bar(df["policy"], df["mean_wait_min"], color="coral")
    axes[1].set_title("Mean wait time by policy")
    axes[1].set_ylabel("Minutes")
    axes[1].tick_params(axis="x", labelsize=7)

    fig.tight_layout()
    chart_path = ARTIFACT_DIR / "policy_comparison_chart.png"
    fig.savefig(chart_path, dpi=150)
    plt.close(fig)

    html_path = ARTIFACT_DIR / "policy_comparison_table.html"
    html_path.write_text(df.to_html(index=False), encoding="utf-8")

    print(f"Saved JSON: {json_path.resolve()}")
    print(f"Saved chart: {chart_path.resolve()}")
    print(f"Saved HTML table: {html_path.resolve()}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
