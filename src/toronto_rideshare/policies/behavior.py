"""Configurable rider and driver behavioral response models."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BehaviorConfig:
    """Elasticities controlling demand/supply response to incentives."""

    rider_price_elasticity: float = -0.3
    driver_bonus_elasticity: float = 0.4
    reposition_acceptance: float = 0.7


@dataclass(frozen=True, slots=True)
class OfferAcceptanceConfig:
    """Assumed driver offer-response model.

    Probability is logistic in offered earnings and pickup burden. Coefficients
    are configurable assumptions, not empirically estimated Toronto behavior.
    """

    intercept: float = 0.5
    earnings_per_cad: float = 0.10
    pickup_minutes_penalty: float = 0.18


def driver_offer_probability(
    driver_earnings_cad: float,
    pickup_min: float,
    *,
    config: OfferAcceptanceConfig | None = None,
) -> float:
    """Return a logistic driver acceptance probability."""
    cfg = config or OfferAcceptanceConfig()
    score = (
        cfg.intercept
        + cfg.earnings_per_cad * driver_earnings_cad
        - cfg.pickup_minutes_penalty * pickup_min
    )
    return 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, score))))


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


def rider_request_probability(
    rider_adjustment_cad: float,
    *,
    config: BehaviorConfig | None = None,
) -> float:
    """Probability an arrived rider remains after seeing an adjustment."""
    cfg = config or BehaviorConfig()
    response = 1.0 + cfg.rider_price_elasticity * (rider_adjustment_cad / 5.0)
    return max(0.0, min(1.0, response))


def apply_driver_bonus_response(
    base_probability: float,
    driver_bonus_cad: float,
    *,
    config: BehaviorConfig | None = None,
) -> float:
    """Apply the assumed bonus-driven supply response to an offer probability."""
    cfg = config or BehaviorConfig()
    multiplier = 1.0 + cfg.driver_bonus_elasticity * (driver_bonus_cad / 12.0)
    return max(0.0, min(1.0, base_probability * multiplier))


def driver_accepts_reposition(
    *,
    config: BehaviorConfig | None = None,
    rng_value: float = 0.5,
) -> bool:
    """Stochastic acceptance of repositioning offers."""
    cfg = config or BehaviorConfig()
    return rng_value < cfg.reposition_acceptance
