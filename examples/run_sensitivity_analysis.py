"""Run fleet size × demand multiplier sensitivity grid."""

from __future__ import annotations

import json
from pathlib import Path

from toronto_rideshare.experiments import run_sensitivity_analysis


def main() -> None:
    result = run_sensitivity_analysis("configs/experiments/baseline_run.yaml")
    out_dir = Path("artifacts/task_sensitivity")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "sensitivity_grid.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Saved {path}")
    for row in result["grid"]:
        print(row)


if __name__ == "__main__":
    main()
