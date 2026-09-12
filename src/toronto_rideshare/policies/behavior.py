"""Configurable rider and driver behavioral response models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BehaviorConfig:
    """Elasticities controlling demand/supply response to incentives."""

    rider_price_elasticity: float = -0.3
    driver_bonus_elasticity: float = 0.4
    reposition_acceptance: float = 0.7


def effective_demand_multiplier(
    base_multiplier: float,
    rider_adjustment_cad: float,
    *,
    config: BehaviorConfig | None = None,
) -> float:
    """Higher rider premiums reduce effective demand (documented assumption)."""
    cfg = config or BehaviorConfig()
    adjustment = 1.0 + cfg.rider_price_elasticity * (rider_adjustment_cad / 5.0)
    return max(0.1, base_multiplier * adjustment)


def effective_supply_multiplier(
    base_fleet: int,
    driver_bonus_cad: float,
    *,
    config: BehaviorConfig | None = None,
) -> float:
    """Driver bonuses increase effective idle supply availability."""
    cfg = config or BehaviorConfig()
    boost = 1.0 + cfg.driver_bonus_elasticity * (driver_bonus_cad / 12.0)
    return max(0.5, min(2.0, boost * base_fleet / max(base_fleet, 1)))


def driver_accepts_reposition(
    *,
    config: BehaviorConfig | None = None,
    rng_value: float = 0.5,
) -> bool:
    """Stochastic acceptance of repositioning offers."""
    cfg = config or BehaviorConfig()
    return rng_value < cfg.reposition_acceptance
