"""Baseline fare and compensation (P0)."""

from __future__ import annotations

from dataclasses import dataclass

BASE_FARE_CAD = 3.50
PER_KM_CAD = 1.10
PER_MIN_CAD = 0.35
DRIVER_SHARE = 0.75


@dataclass(frozen=True, slots=True)
class FareBreakdown:
    baseline_fare_cad: float
    rider_adjustment_cad: float
    driver_bonus_cad: float
    rider_payment_cad: float
    driver_earnings_cad: float
    platform_contribution_cad: float


def compute_fare(
    distance_km: float,
    duration_min: float,
    *,
    rider_adjustment_cad: float = 0.0,
    driver_bonus_cad: float = 0.0,
) -> FareBreakdown:
    """Independent two-sided pricing: P_r = P0 + a, E_r = E0 + b."""
    baseline = BASE_FARE_CAD + PER_KM_CAD * distance_km + PER_MIN_CAD * duration_min
    rider_adjustment_cad = max(-baseline, rider_adjustment_cad)
    rider_payment = baseline + rider_adjustment_cad
    driver_earnings = baseline * DRIVER_SHARE + driver_bonus_cad
    platform = rider_payment - driver_earnings
    return FareBreakdown(
        baseline_fare_cad=baseline,
        rider_adjustment_cad=rider_adjustment_cad,
        driver_bonus_cad=driver_bonus_cad,
        rider_payment_cad=rider_payment,
        driver_earnings_cad=driver_earnings,
        platform_contribution_cad=platform,
    )
