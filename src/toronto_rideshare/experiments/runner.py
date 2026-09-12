"""Run reproducible simulation experiments from YAML config."""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from toronto_rideshare.config import load_config
from toronto_rideshare.demand import generate_trips
from toronto_rideshare.marketplace.matching import RoutingContext
from toronto_rideshare.policies.behavior import BehaviorConfig
from toronto_rideshare.policies.registry import POLICY_REGISTRY, PolicyId
from toronto_rideshare.simulation import SimulationClock, SimulationEngine
from toronto_rideshare.supply import initialize_fleet
from toronto_rideshare.zones import toronto_zone_cells


def _time_to_min(value: str) -> float:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _load_routing_context(config: dict[str, Any]) -> RoutingContext | None:
    network_cfg = config.get("network", {})
    graph_path = network_cfg.get("graph_path")
    if not graph_path or not Path(graph_path).exists():
        return None

    from toronto_rideshare.network import load_graph

    graph = load_graph(graph_path)
    profile = None
    profile_path = network_cfg.get(
        "traffic_profile_path", "data/processed/edge_traffic_profile.parquet"
    )
    if Path(profile_path).exists():
        from toronto_rideshare.traffic import load_traffic_profile

        profile = load_traffic_profile(profile_path)

    return RoutingContext(
        graph=graph,
        profile=profile,
        use_time_dependent=bool(network_cfg.get("use_time_dependent_routing", True)),
    )


def run_experiment(
    config_path: str | Path,
    *,
    policy_id: PolicyId | str | None = None,
    routing: RoutingContext | None = None,
) -> dict[str, Any]:
    """Execute one simulation experiment and return metrics."""
    config = load_config(config_path)
    seed = int(config.get("project", {}).get("random_seed", 42))
    sim_cfg = config.get("simulation", {})
    policy_cfg = config.get("policy", {})

    pid = PolicyId(policy_id or policy_cfg.get("name", PolicyId.P0))
    settings = POLICY_REGISTRY[pid]
    behavior = BehaviorConfig(
        rider_price_elasticity=float(policy_cfg.get("rider_price_elasticity", -0.3)),
        driver_bonus_elasticity=float(policy_cfg.get("driver_bonus_elasticity", 0.4)),
        reposition_acceptance=float(policy_cfg.get("reposition_acceptance", 0.7)),
    )

    zones = sorted(toronto_zone_cells())[:50]
    demand_mult = float(sim_cfg.get("demand_multiplier", 1.0))
    trips = generate_trips(
        zones,
        n_trips=int(20 * demand_mult),
        random_seed=seed,
        demand_multiplier=demand_mult,
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

    routing_ctx = routing if routing is not None else _load_routing_context(config)

    engine = SimulationEngine(
        clock=clock,
        drivers=drivers,
        trips=trips,
        routing=routing_ctx,
        policy_settings=settings,
        behavior=behavior if settings.use_behavior else None,
        policy_cfg=policy_cfg,
    )
    metrics = engine.run()

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "config_path": str(config_path),
        "policy_id": settings.policy_id.value,
        "random_seed": seed,
        "metrics": asdict(metrics),
        "mean_wait_min": engine.waiting.mean_total_wait_min(),
        "reposition_events": engine.reposition_events,
        "used_network_routing": routing_ctx is not None,
    }


def run_policy_comparison(
    config_path: str | Path,
    *,
    policies: tuple[PolicyId, ...] | None = None,
) -> dict[str, Any]:
    """Run P0–P7 on the same random seed for fair comparison."""
    config = load_config(config_path)
    seed = int(config.get("project", {}).get("random_seed", 42))
    routing = _load_routing_context(config)
    policy_list = policies or tuple(PolicyId)

    results: list[dict[str, Any]] = []
    for pid in policy_list:
        result = run_experiment(config_path, policy_id=pid, routing=routing)
        results.append(result)

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "config_path": str(config_path),
        "random_seed": seed,
        "policies": [r["policy_id"] for r in results],
        "results": results,
    }


def run_stochastic_experiments(
    config_path: str | Path,
    *,
    n_replicates: int = 10,
    base_seed: int = 42,
    policy_id: PolicyId | str = PolicyId.P0,
) -> dict[str, Any]:
    """Run repeated experiments with different seeds and report confidence intervals."""
    config = load_config(config_path)
    replicates: list[dict[str, Any]] = []

    for i in range(n_replicates):
        config["project"]["random_seed"] = base_seed + i
        tmp_path = Path("artifacts/task_stochastic/tmp_config.yaml")
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        import yaml

        tmp_path.write_text(yaml.dump(config), encoding="utf-8")
        replicates.append(run_experiment(tmp_path, policy_id=policy_id))

    completed = [r["metrics"]["completed_trips"] for r in replicates]
    waits = [r["mean_wait_min"] for r in replicates]

    def _ci(values: list[float]) -> dict[str, float]:
        if len(values) < 2:
            v = values[0] if values else 0.0
            return {"mean": v, "std": 0.0, "ci95_low": v, "ci95_high": v}
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        margin = 1.96 * stdev / (len(values) ** 0.5)
        return {
            "mean": mean,
            "std": stdev,
            "ci95_low": mean - margin,
            "ci95_high": mean + margin,
        }

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "config_path": str(config_path),
        "policy_id": str(policy_id),
        "n_replicates": n_replicates,
        "completed_trips": _ci([float(v) for v in completed]),
        "mean_wait_min": _ci(waits),
        "replicates": replicates,
    }


def run_sensitivity_analysis(
    config_path: str | Path,
    *,
    fleet_sizes: tuple[int, ...] = (10, 20, 40),
    demand_multipliers: tuple[float, ...] = (0.5, 1.0, 1.5),
) -> dict[str, Any]:
    """Grid search over fleet size and demand multiplier."""
    config = load_config(config_path)
    grid_results: list[dict[str, Any]] = []

    for fleet in fleet_sizes:
        for demand in demand_multipliers:
            config["simulation"]["fleet_size"] = fleet
            config["simulation"]["demand_multiplier"] = demand
            tmp_path = Path("artifacts/task_sensitivity/tmp_config.yaml")
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            import yaml

            tmp_path.write_text(yaml.dump(config), encoding="utf-8")
            result = run_experiment(tmp_path)
            grid_results.append(
                {
                    "fleet_size": fleet,
                    "demand_multiplier": demand,
                    "completed_trips": result["metrics"]["completed_trips"],
                    "unserved_trips": result["metrics"]["unserved_trips"],
                    "mean_wait_min": result["mean_wait_min"],
                }
            )

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "config_path": str(config_path),
        "grid": grid_results,
    }


def save_experiment_result(result: dict[str, Any], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    name = result.get("policy_id", result.get("random_seed", "run"))
    safe_name = str(name).replace("/", "_")
    path = out / f"experiment_{safe_name}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return path
