"""Run reproducible simulation experiments from YAML config."""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from toronto_rideshare.demand import generate_trips
from toronto_rideshare.manifest import run_manifest
from toronto_rideshare.marketplace.matching import RoutingContext
from toronto_rideshare.policies.behavior import BehaviorConfig, OfferAcceptanceConfig
from toronto_rideshare.policies.registry import POLICY_REGISTRY, PolicyId
from toronto_rideshare.scenario import ScenarioConfig, stream_seed, time_minutes
from toronto_rideshare.simulation import SimulationClock, SimulationEngine
from toronto_rideshare.supply import initialize_fleet
from toronto_rideshare.zones import toronto_zone_cells


def _time_to_min(value: str) -> float:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def load_routing_context(config: dict[str, Any]) -> RoutingContext | None:
    """Load the optional graph/profile routing context declared by config."""
    network_cfg = config.get("network", {})
    if network_cfg.get("mode") == "demo":
        return None
    graph_path = network_cfg.get("graph_path")
    if not graph_path or not Path(graph_path).exists():
        if network_cfg.get("mode") == "network_research":
            raise ValueError(
                "Network research requires a local GraphML road graph. Build it first."
            )
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
        strict=network_cfg.get("mode") == "network_research",
        use_time_dependent=bool(network_cfg.get("use_time_dependent_routing", True)),
    )


def create_engine(
    source, *, policy_id=None, routing=None, random_seed=None, load_configured_routing=True
):
    """Shared entry point for UI and CLI; never mutates the supplied scenario."""
    config = ScenarioConfig.from_source(source).as_dict()
    if policy_id is not None:
        config["policy"]["name"] = str(policy_id)
    if random_seed is not None:
        config["project"]["random_seed"] = random_seed
    config = ScenarioConfig.from_source(config).as_dict()
    sim, policy = config["simulation"], config["policy"]
    seed = config["project"]["random_seed"]
    legacy = config["behavior"]["profile"] == "legacy_v0.4"
    settings = POLICY_REGISTRY[PolicyId(policy["name"])]
    behavior = BehaviorConfig(
        policy["rider_price_elasticity"],
        policy["driver_bonus_elasticity"],
        policy["reposition_acceptance"],
    )
    context = (
        routing
        if routing is not None
        else (load_routing_context(config) if load_configured_routing else None)
    )
    if config["network"]["mode"] == "network_research" and context is None:
        raise ValueError("Network research cannot run without a graph")
    zones = list(toronto_zone_cells())
    trips = generate_trips(
        zones,
        n_trips=sim["base_trip_count"],
        start_time_min=time_minutes(sim["start_time"]),
        end_time_min=time_minutes(sim["end_time"]),
        random_seed=seed if legacy else stream_seed(seed, "demand"),
        demand_multiplier=sim["demand_multiplier"],
        demand_profile=sim["demand_profile"],
        request_probability=sim["request_probability"],
    )
    drivers = initialize_fleet(
        zones,
        fleet_size=sim["fleet_size"],
        random_seed=seed if legacy else stream_seed(seed, "fleet"),
    )
    if context and config["network"]["mode"] == "network_research":
        import numpy as np

        from toronto_rideshare.zones import lat_lon_to_zone, point_is_in_toronto

        eligible = sorted(
            (int(n), float(d["y"]), float(d["x"]))
            for n, d in context.graph.nodes(data=True)
            if point_is_in_toronto(d["y"], d["x"]) and context.graph.degree(n) > 0
        )
        if not eligible:
            raise ValueError("Graph contains no eligible road nodes inside Toronto")
        # Uniform eligible road-node baseline; reported separately from demo placement.
        from dataclasses import replace

        rng = np.random.default_rng(stream_seed(seed, "network_demand"))
        from toronto_rideshare.demand.profiles import location_weights, region_for_location

        regions = [region_for_location(lat, lon) for _, lat, lon in eligible]
        sampled = []
        for trip in trips:
            if sim["demand_profile"] == "synthetic_daily":
                origin_weights = location_weights(regions, trip.request_time_min)
                dest_weights = location_weights(regions, trip.request_time_min, destination=True)
                _, lat, lon = eligible[int(rng.choice(len(eligible), p=origin_weights))]
                _, dlat, dlon = eligible[int(rng.choice(len(eligible), p=dest_weights))]
            else:
                _, lat, lon = eligible[int(rng.integers(len(eligible)))]
                _, dlat, dlon = eligible[int(rng.integers(len(eligible)))]
            sampled.append(
                replace(
                    trip,
                    origin_lat=lat,
                    origin_lon=lon,
                    destination_lat=dlat,
                    destination_lon=dlon,
                    origin_zone=lat_lon_to_zone(lat, lon),
                    destination_zone=lat_lon_to_zone(dlat, dlon),
                )
            )
        trips = sampled
        rng = np.random.default_rng(stream_seed(seed, "network_fleet"))
        for driver in drivers:
            _, driver.lat, driver.lon = eligible[int(rng.integers(len(eligible)))]
            driver.zone = lat_lon_to_zone(driver.lat, driver.lon)
    engine = SimulationEngine(
        clock=SimulationClock(
            time_minutes(sim["start_time"]),
            time_minutes(sim["end_time"]),
            sim["decision_interval_minutes"],
        ),
        drivers=drivers,
        trips=trips,
        routing=context,
        policy_settings=settings,
        behavior=behavior if not legacy or settings.use_behavior else None,
        behavior_profile=config["behavior"]["profile"],
        additional_bonus_response=config["behavior"]["additional_bonus_response"],
        acceptance=OfferAcceptanceConfig(
            policy["acceptance_intercept"],
            policy["acceptance_earnings_per_cad"],
            policy["acceptance_pickup_minutes_penalty"],
        ),
        random_seed=seed if legacy else stream_seed(seed, "behavior"),
        policy_cfg=policy,
        matching_strategy=None
        if policy["matching_strategy"] == "policy_default"
        else policy["matching_strategy"],
        max_wait_time_min=sim["rider_max_wait_minutes"],
    )
    engine.scenario = config
    return engine


def run_experiment(
    config_path, *, policy_id=None, routing=None, random_seed=None, load_configured_routing=True
):
    engine = create_engine(
        config_path,
        policy_id=policy_id,
        routing=routing,
        random_seed=random_seed,
        load_configured_routing=load_configured_routing,
    )
    config = engine.scenario
    settings, clock = engine.policy_settings, engine.clock
    seed = config["project"]["random_seed"]
    policy_cfg = config["policy"]
    behavior = engine.behavior or BehaviorConfig()
    start_time, trips, routing_ctx = clock.start_time_min, engine.trips, engine.routing
    metrics = engine.run()
    waits = sorted(record.total_wait_min for record in engine.waiting.records.values())

    def percentile(values: list[float], fraction: float) -> float:
        if not values:
            return 0.0
        position = (len(values) - 1) * fraction
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        return values[lower] + (values[upper] - values[lower]) * (position - lower)

    route_count = sum(metrics.routing_mode_counts.values())
    routing_mode_share = {
        mode: count / route_count for mode, count in metrics.routing_mode_counts.items()
    }

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "manifest": run_manifest(config, engine),
        "config_path": str(config_path)
        if isinstance(config_path, (str, Path))
        else "applied scenario",
        "policy_id": settings.policy_id.value,
        "random_seed": seed,
        "simulation_start_time_min": start_time,
        "simulation_end_time_min": clock.end_time_min,
        "generated_trip_count": len(trips),
        "metrics": asdict(metrics),
        "mean_wait_min": engine.waiting.mean_total_wait_min(),
        "p50_wait_min": percentile(waits, 0.50),
        "p95_wait_min": percentile(waits, 0.95),
        "reposition_events": engine.reposition_events,
        "used_network_routing": routing_ctx is not None,
        "routing_mode": engine.last_snapshot["routing_mode"],
        "routing_fallback_reason": engine.last_snapshot["routing_fallback_reason"],
        "matching_strategy": engine.last_snapshot["matching_strategy"],
        "matching_backend": engine.last_snapshot["matching_backend"],
        "routing_mode_share": routing_mode_share,
        "zone_state": engine.last_snapshot["zone_state"],
        "policy_objective": settings.objective,
        "policy_strategy": settings.strategy,
        "policy_assumptions": {
            "behavior_enabled": engine.behavior is not None,
            "rider_price_elasticity": behavior.rider_price_elasticity,
            "driver_bonus_elasticity": behavior.driver_bonus_elasticity,
            "reposition_acceptance": behavior.reposition_acceptance,
            "offer_acceptance": asdict(engine.acceptance),
            "rider_max_wait_minutes": engine.max_wait_time_min,
            "predicted_demand_response_per_cad": float(
                policy_cfg.get("predicted_demand_response_per_cad", 0.06)
            ),
            "predicted_supply_response_per_cad": float(
                policy_cfg.get("predicted_supply_response_per_cad", 0.04)
            ),
        },
    }


def run_policy_comparison(
    config_path: str | Path,
    *,
    policies: tuple[PolicyId, ...] | None = None,
    load_configured_routing: bool = True,
) -> dict[str, Any]:
    """Run P0–P7 on the same random seed for fair comparison."""
    config = ScenarioConfig.from_source(config_path).as_dict()
    seed = int(config.get("project", {}).get("random_seed", 42))
    routing = load_routing_context(config) if load_configured_routing else None
    policy_list = tuple(dict.fromkeys((PolicyId.P0, *(policies or tuple(PolicyId)))))

    results: list[dict[str, Any]] = []
    for pid in policy_list:
        result = run_experiment(
            config_path,
            policy_id=pid,
            routing=routing,
            load_configured_routing=load_configured_routing,
        )
        results.append(result)

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "config_path": str(config_path),
        "random_seed": seed,
        "policies": [r["policy_id"] for r in results],
        "results": results,
    }


def run_repeated_policy_comparison(
    config_path: str | Path,
    *,
    policies: tuple[PolicyId, ...] | None = None,
    n_replicates: int = 30,
    base_seed: int | None = None,
    load_configured_routing: bool = True,
) -> dict[str, Any]:
    """Compare policies with common random numbers and normal 95% intervals."""
    if n_replicates < 1:
        raise ValueError("n_replicates must be at least 1")
    config = ScenarioConfig.from_source(config_path).as_dict()
    first_seed = int(
        base_seed if base_seed is not None else config.get("project", {}).get("random_seed", 42)
    )
    policy_list = tuple(dict.fromkeys((PolicyId.P0, *(policies or tuple(PolicyId)))))
    routing = load_routing_context(config) if load_configured_routing else None
    replicates = [
        run_experiment(
            config_path,
            policy_id=policy,
            routing=routing,
            random_seed=seed,
            load_configured_routing=load_configured_routing,
        )
        for seed in range(first_seed, first_seed + n_replicates)
        for policy in policy_list
    ]

    metric_getters = {
        "completed_trips": lambda row: row["metrics"]["completed_trips"],
        "service_rate": lambda row: row["metrics"]["service_rate"],
        "unserved_trips": lambda row: row["metrics"]["unserved_trips"],
        "mean_wait_min": lambda row: row["mean_wait_min"],
        "p95_wait_min": lambda row: row["p95_wait_min"],
        "mean_pickup_time_min": lambda row: row["metrics"]["mean_pickup_time_min"],
        "mean_trip_time_min": lambda row: row["metrics"]["mean_trip_time_min"],
        "in_progress_trips": lambda row: row["metrics"]["in_progress_trips"],
        "cancelled_trips": lambda row: row["metrics"]["cancelled_trips"],
        "waiting_trips": lambda row: row["metrics"]["waiting_trips"],
        "price_declined_trips": lambda row: row["metrics"]["rider_price_declines"],
        "elapsed_reposition_min": lambda row: row["metrics"]["elapsed_reposition_min"],
        "acceptance_rate": lambda row: row["metrics"]["acceptance_rate"],
        "rider_payment_cad": lambda row: row["metrics"]["total_rider_payment_cad"],
        "driver_earnings_cad": lambda row: row["metrics"]["total_driver_earnings_cad"],
        "subsidy_spend_cad": lambda row: row["metrics"]["subsidy_spend_cad"],
        "platform_net_revenue_cad": lambda row: row["metrics"]["platform_net_revenue_cad"],
        "reposition_events": lambda row: row["reposition_events"],
        "utilization_rate": lambda row: row["metrics"]["utilization_rate"],
    }

    def interval(values: list[float], *, bounded: bool = False) -> dict[str, float]:
        mean = statistics.mean(values)
        if len(values) == 1:
            return {"mean": mean, "ci95_low": None, "ci95_high": None}
        from scipy.stats import t

        margin = (
            float(t.ppf(0.975, len(values) - 1)) * statistics.stdev(values) / len(values) ** 0.5
        )
        low, high = mean - margin, mean + margin
        if bounded:
            low, high = max(0.0, low), min(1.0, high)
        return {
            "mean": mean,
            "ci95_low": low,
            "ci95_high": high,
        }

    aggregates = []
    for policy in policy_list:
        rows = [row for row in replicates if row["policy_id"] == policy.value]
        aggregates.append(
            {
                "policy_id": policy.value,
                "metrics": {
                    name: interval(
                        [float(getter(row)) for row in rows],
                        bounded=name.endswith("_rate"),
                    )
                    for name, getter in metric_getters.items()
                },
                "paired_delta_vs_p0": {
                    name: interval(
                        [
                            float(getter(row)) - float(getter(base))
                            for row, base in zip(
                                rows,
                                [r for r in replicates if r["policy_id"] == PolicyId.P0],
                                strict=True,
                            )
                        ]
                    )
                    for name, getter in metric_getters.items()
                },
                "policy_strategy": rows[0]["policy_strategy"],
                "policy_objective": rows[0]["policy_objective"],
            }
        )

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "config_path": str(config_path),
        "seeds": list(range(first_seed, first_seed + n_replicates)),
        "common_random_numbers": config["behavior"]["profile"] == "shared",
        "reference_policy": PolicyId.P0.value,
        "interval_method": "paired Student-t; unavailable for one replicate",
        "aggregates": aggregates,
        "replicates": replicates,
    }


def run_stochastic_experiments(
    config_path: str | Path,
    *,
    n_replicates: int = 10,
    base_seed: int = 42,
    policy_id: PolicyId | str = PolicyId.P0,
) -> dict[str, Any]:
    """Run repeated experiments with different seeds and report confidence intervals."""
    config = ScenarioConfig.from_source(config_path).as_dict()
    replicates: list[dict[str, Any]] = []

    for i in range(n_replicates):
        config["project"]["random_seed"] = base_seed + i
        replicates.append(run_experiment(config, policy_id=policy_id))

    completed = [r["metrics"]["completed_trips"] for r in replicates]
    waits = [r["mean_wait_min"] for r in replicates]

    def _ci(values: list[float]) -> dict[str, float]:
        if len(values) < 2:
            v = values[0] if values else 0.0
            return {"mean": v, "std": None, "ci95_low": None, "ci95_high": None}
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        from scipy.stats import t

        margin = float(t.ppf(0.975, len(values) - 1)) * stdev / (len(values) ** 0.5)
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
    config = ScenarioConfig.from_source(config_path).as_dict()
    grid_results: list[dict[str, Any]] = []

    for fleet in fleet_sizes:
        for demand in demand_multipliers:
            config["simulation"]["fleet_size"] = fleet
            config["simulation"]["demand_multiplier"] = demand
            result = run_experiment(config)
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
