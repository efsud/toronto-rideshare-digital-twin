"""Policy identifiers and zone-level adjustment helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from toronto_rideshare.optimization.pricing_opt import optimize_zone_pricing
from toronto_rideshare.policies.incentives import driver_bonus_cad
from toronto_rideshare.policies.pricing import rider_adjustment_cad


class PolicyId(StrEnum):
    P0 = "P0_fixed_baseline"
    P1 = "P1_rider_pricing"
    P2 = "P2_driver_bonuses"
    P3 = "P3_two_sided_rules"
    P4 = "P4_ortools_lp"
    P5 = "P5_repositioning"
    P6 = "P6_rules_plus_reposition"
    P7 = "P7_full_stack"


@dataclass(frozen=True, slots=True)
class PolicySettings:
    policy_id: PolicyId
    use_rider_pricing: bool = False
    use_driver_bonuses: bool = False
    use_ortools: bool = False
    use_repositioning: bool = False
    use_behavior: bool = False


POLICY_REGISTRY: dict[PolicyId, PolicySettings] = {
    PolicyId.P0: PolicySettings(PolicyId.P0),
    PolicyId.P1: PolicySettings(PolicyId.P1, use_rider_pricing=True),
    PolicyId.P2: PolicySettings(PolicyId.P2, use_driver_bonuses=True),
    PolicyId.P3: PolicySettings(
        PolicyId.P3, use_rider_pricing=True, use_driver_bonuses=True
    ),
    PolicyId.P4: PolicySettings(
        PolicyId.P4,
        use_rider_pricing=True,
        use_driver_bonuses=True,
        use_ortools=True,
    ),
    PolicyId.P5: PolicySettings(PolicyId.P5, use_repositioning=True),
    PolicyId.P6: PolicySettings(
        PolicyId.P6,
        use_rider_pricing=True,
        use_driver_bonuses=True,
        use_repositioning=True,
    ),
    PolicyId.P7: PolicySettings(
        PolicyId.P7,
        use_rider_pricing=True,
        use_driver_bonuses=True,
        use_ortools=True,
        use_repositioning=True,
        use_behavior=True,
    ),
}


def zone_adjustments_from_imbalance(
    zone_imbalance: dict[str, dict[str, float]],
    settings: PolicySettings,
    policy_cfg: dict[str, Any],
) -> dict[str, tuple[float, float]]:
    """Compute per-zone rider adjustments and driver bonuses."""
    rider_cap = float(policy_cfg.get("max_rider_premium_cad", 5.0))
    bonus_cap = float(policy_cfg.get("max_driver_bonus_cad", 12.0))
    budget = float(policy_cfg.get("subsidy_budget_cad", 500.0))

    if settings.use_ortools and (settings.use_rider_pricing or settings.use_driver_bonuses):
        decisions = optimize_zone_pricing(
            zone_imbalance,
            rider_cap=rider_cap,
            bonus_cap=bonus_cap,
            total_budget_cad=budget,
        )
        return {
            d.zone: (
                d.rider_adjustment_cad if settings.use_rider_pricing else 0.0,
                d.driver_bonus_cad if settings.use_driver_bonuses else 0.0,
            )
            for d in decisions
        }

    adjustments: dict[str, tuple[float, float]] = {}
    for zone, stats in zone_imbalance.items():
        imb = float(stats["imbalance"])
        rider = rider_adjustment_cad(imb, cap=rider_cap) if settings.use_rider_pricing else 0.0
        bonus = driver_bonus_cad(imb, cap=bonus_cap) if settings.use_driver_bonuses else 0.0
        adjustments[zone] = (rider, bonus)
    return adjustments
