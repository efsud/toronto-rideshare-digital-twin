"""One resolved, validated scenario for both the dashboard and experiments."""

from __future__ import annotations

import copy
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from toronto_rideshare.config import load_config

DEFAULTS = {
    "project": {"random_seed": 42, "model_version": "0.6.0.dev0"},
    "simulation": {
        "start_time": "00:00",
        "end_time": "24:00",
        "decision_interval_minutes": 5.0,
        "fleet_size": 60,
        "base_trip_count": 1200,
        "demand_multiplier": 1.0,
        "demand_profile": "synthetic_daily",
        "request_probability": 0.8,
        "rider_max_wait_minutes": 15.0,
    },
    "network": {
        "mode": "demo",
        "graph_path": "data/processed/toronto_drive.graphml",
        "traffic_profile_path": "data/processed/edge_traffic_profile.parquet",
        "use_time_dependent_routing": True,
    },
    "behavior": {
        "profile": "shared",
        "additional_bonus_response": False,
        "marketplace_model": "driver_choice",
        "rider_intercept": 2.0,
        "rider_price_per_cad": 0.08,
        "driver_occupied_penalty": 0.02,
    },
    "policy": {
        "name": "P0_fixed_baseline",
        "matching_strategy": "policy_default",
        "max_rider_premium_cad": 5.0,
        "max_driver_bonus_cad": 12.0,
        "subsidy_budget_cad": 500.0,
        "fairness_bound_cad": 3.0,
        "rider_price_elasticity": -0.3,
        "driver_bonus_elasticity": 0.4,
        "reposition_acceptance": 0.7,
        "acceptance_intercept": 0.5,
        "acceptance_earnings_per_cad": 0.1,
        "acceptance_pickup_minutes_penalty": 0.18,
        "od_origin_gain": 0.5,
        "od_transfer_gain": 1.0,
        "od_discount_gain": 0.5,
        "predicted_demand_response_per_cad": 0.06,
        "predicted_supply_response_per_cad": 0.04,
    },
}


def time_minutes(value: str) -> float:
    try:
        hour, minute = map(int, value.split(":"))
        if not ((0 <= hour <= 23 and 0 <= minute <= 59) or (hour == 24 and minute == 0)):
            raise ValueError
        return float(hour * 60 + minute)
    except (ValueError, AttributeError) as exc:
        raise ValueError("Times must use HH:MM within one day (24:00 allowed at the end)") from exc


def stream_seed(seed: int, stream: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{seed}:{stream}".encode()).digest()[:8], "big")


@dataclass(frozen=True)
class ScenarioConfig:
    """Validated input; as_dict returns an independent copy for safe UI editing."""

    _data: dict[str, Any]

    @classmethod
    def from_source(cls, source: Any) -> ScenarioConfig:
        if isinstance(source, cls):
            return cls(copy.deepcopy(source._data))
        raw = load_config(source) if isinstance(source, (str, Path)) else copy.deepcopy(source)
        if not isinstance(raw, dict):
            raise ValueError("Scenario must be a mapping")
        data = copy.deepcopy(DEFAULTS)
        for section, values in raw.items():
            if section in data:
                if not isinstance(values, dict):
                    raise ValueError(f"{section} must be a mapping")
                data[section].update(values)
        if data["policy"]["name"] == "fixed_baseline":
            data["policy"]["name"] = "P0_fixed_baseline"
        from toronto_rideshare.policies.registry import PolicyId

        PolicyId(data["policy"]["name"])
        sim, policy = data["simulation"], data["policy"]
        if time_minutes(sim["end_time"]) < time_minutes(sim["start_time"]):
            raise ValueError("End time must not precede start time")
        for section in ("project", "simulation", "policy", "behavior"):
            for key, value in data[section].items():
                if isinstance(value, (int, float)) and not math.isfinite(value):
                    raise ValueError(f"{key} must be finite")
        for key in ("fleet_size", "base_trip_count"):
            value = sim[key]
            if isinstance(value, bool) or int(value) != value or value < 0:
                raise ValueError(f"{key} must be a nonnegative integer")
            sim[key] = int(value)
        seed = data["project"]["random_seed"]
        if isinstance(seed, bool) or int(seed) != seed or seed < 0:
            raise ValueError("random_seed must be a nonnegative integer")
        if sim["decision_interval_minutes"] <= 0 or sim["rider_max_wait_minutes"] <= 0:
            raise ValueError("Decision interval and queue wait must be positive")
        if time_minutes(sim["start_time"]) >= 1440:
            raise ValueError("Start time must precede 24:00")
        if sim["demand_profile"] not in ("uniform", "synthetic_daily"):
            raise ValueError("Unknown demand profile")
        if not 0 <= sim["request_probability"] <= 1:
            raise ValueError("Request probability must be in [0,1]")
        if sim["demand_multiplier"] < 0:
            raise ValueError("Demand multiplier must be nonnegative")
        if not 0 <= policy["reposition_acceptance"] <= 1:
            raise ValueError("Reposition acceptance must be a probability")
        if policy["rider_price_elasticity"] > 0:
            raise ValueError("Rider price response must be nonpositive")
        for key in (
            "max_rider_premium_cad",
            "max_driver_bonus_cad",
            "subsidy_budget_cad",
            "fairness_bound_cad",
            "driver_bonus_elasticity",
            "acceptance_earnings_per_cad",
            "acceptance_pickup_minutes_penalty",
            "predicted_demand_response_per_cad",
            "predicted_supply_response_per_cad",
        ):
            if policy[key] < 0:
                raise ValueError(f"{key} must be nonnegative")
        if data["behavior"]["marketplace_model"] not in ("legacy_offers", "driver_choice"):
            raise ValueError("Unknown marketplace model")
        for key in ("rider_price_per_cad", "driver_occupied_penalty"):
            if data["behavior"][key] < 0:
                raise ValueError(f"{key} must be nonnegative")
        for key in ("od_origin_gain", "od_transfer_gain", "od_discount_gain"):
            if policy[key] < 0:
                raise ValueError(f"{key} must be nonnegative")
        if (
            policy["name"] == "adaptive_od"
            and data["behavior"]["marketplace_model"] != "driver_choice"
        ):
            raise ValueError("Adaptive OD pricing requires the driver-choice marketplace")
        if data["behavior"]["marketplace_model"] == "driver_choice":
            if data["behavior"]["profile"] != "shared":
                raise ValueError("Driver choice requires shared behavior")
            if policy["name"] not in ("P0_fixed_baseline", "P5_repositioning", "adaptive_od"):
                raise ValueError("The daily marketplace supports only the three active policies")
            if policy["matching_strategy"] != "policy_default":
                raise ValueError(
                    "Daily policies share driver choice; matching overrides are unavailable"
                )
        if policy["matching_strategy"] not in ("policy_default", "greedy", "optimal_batch"):
            raise ValueError("Unknown matching strategy")
        if data["network"]["mode"] not in ("demo", "network_research"):
            raise ValueError("Unknown routing mode")
        if data["behavior"]["profile"] not in ("shared", "legacy_v0.4"):
            raise ValueError("Unknown behavior profile")
        return cls(data)

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)
