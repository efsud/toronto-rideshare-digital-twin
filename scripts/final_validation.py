"""Task 37 — run core validation suite and write summary."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from toronto_rideshare.experiments import run_experiment

OUTPUT = Path("artifacts/task_37_final_validation/validation_summary.json")


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pytest = subprocess.run([sys.executable, "-m", "pytest", "-q"], capture_output=True, text=True)
    experiment = run_experiment("configs/experiments/baseline_run.yaml")
    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "pytest_exit_code": pytest.returncode,
        "pytest_output_tail": pytest.stdout.splitlines()[-3:],
        "experiment_metrics": experiment.get("metrics"),
    }
    OUTPUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT.resolve()}")
    if pytest.returncode != 0:
        raise SystemExit(pytest.returncode)


if __name__ == "__main__":
    main()
