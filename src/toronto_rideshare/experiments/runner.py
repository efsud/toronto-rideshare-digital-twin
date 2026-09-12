"""Run reproducible simulation experiments from YAML config."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from toronto_rideshare.config import load_config
from toronto_rideshare.demand import generate_trips
from toronto_rideshare.simulation import SimulationClock, SimulationEngine
from toronto_rideshare.supply import initialize_fleet
from toronto_rideshare.zones import toronto_zone_cells


def run_experiment(config_path: str | Path) -> dict[str, Any]:
    """Execute one baseline simulation experiment and return metrics."""
    config = load_config(config_path)
    seed = int(config.get("project", {}).get("random_seed", 42))
    sim_cfg = config.get("simulation", {})
    zones = sorted(toronto_zone_cells())[:50]  # manageable subset for dev

    trips = generate_trips(
        zones,
        n_trips=int(20 * sim_cfg.get("demand_multiplier", 1.0)),
        random_seed=seed,
        demand_multiplier=float(sim_cfg.get("demand_multiplier", 1.0)),
    )
    drivers = initialize_fleet(
        zones,
        fleet_size=int(sim_cfg.get("fleet_size", 10)),
        random_seed=seed,
    )
    clock = SimulationClock(
        end_time_min=_time_to_min(sim_cfg.get("end_time", "10:00")),
        step_min=float(sim_cfg.get("decision_interval_minutes", 5)),
    )
    engine = SimulationEngine(clock=clock, drivers=drivers, trips=trips)
    metrics = engine.run()

    result = {
        "timestamp": datetime.now(UTC).isoformat(),
        "config_path": str(config_path),
        "random_seed": seed,
        "metrics": asdict(metrics),
        "mean_wait_min": engine.waiting.mean_total_wait_min(),
    }
    return result


def _time_to_min(value: str) -> float:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def save_experiment_result(result: dict[str, Any], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"experiment_{result['random_seed']}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return path
