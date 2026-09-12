"""Run sensitivity analysis grid from configs/experiments/sensitivity.yaml."""

from __future__ import annotations

import json
from pathlib import Path

from toronto_rideshare.experiments import run_sensitivity_analysis

ARTIFACT_DIR = Path("artifacts/task_sensitivity")


def main() -> None:
    config_path = Path("configs/experiments/sensitivity.yaml")
    result = run_sensitivity_analysis(config_path)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACT_DIR / "sensitivity_results.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Saved {len(result['grid'])} sensitivity runs to {out.resolve()}")


if __name__ == "__main__":
    main()
